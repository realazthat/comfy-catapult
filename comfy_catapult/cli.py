# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT
#
# The Comfy Catapult project requires contributions made to this file be licensed
# under the MIT license or a compatible open source license. See LICENSE.md for
# the license text.
"""
CLI to run a ComfyUI API Workflow against a ComfyUI instance.
"""
import argparse
import asyncio
import json
import logging
import os
import sys
import uuid
import warnings
from datetime import datetime, timezone
from pathlib import Path
from shutil import get_terminal_size
from typing import List, Optional, Tuple

import anyio
import colorama
from attr import dataclass
from rich.console import Console
from rich_argparse import RichHelpFormatter
from slugify import slugify

from . import _build_version
from .api_client import ComfyAPIClient
from .api_client_base import ComfyAPIClientBase
from .catapult import ComfyCatapult
from .catapult_base import ComfyCatapultBase, JobStatus
from .comfy_schema import APINodeID, APISystemStats
from .comfy_utils import YamlDump
from .remote_file_api_comfy import ComfySchemeRemoteFileAPI
from .remote_file_api_generic import GenericRemoteFileAPI

logger = logging.getLogger(__name__)


def _GetProgramName() -> str:
  if __package__:
    # Use __package__ to get the base package name
    base_module_path = __package__
    # Infer the module name from the file path, with assumptions about the structure
    module_name = Path(__file__).stem
    # Construct what might be the intended full module path
    full_module_path = f'{base_module_path}.{module_name}' if base_module_path else module_name
    return f'python -m {full_module_path}'
  else:
    return sys.argv[0]


class _CustomRichHelpFormatter(RichHelpFormatter):

  def __init__(self, *args, **kwargs):
    if kwargs.get('width') is None:
      width, _ = get_terminal_size()
      if width == 0:
        warnings.warn('Terminal width was set to 0, using default width of 80.',
                      RuntimeWarning,
                      stacklevel=0)
        # This is the default in get_terminal_size().
        width = 80
      # This is what HelpFormatter does to the width returned by
      # `get_terminal_size()`.
      width -= 2
      kwargs['width'] = width
    super().__init__(*args, **kwargs)


async def GetWorkflow(workflow_path: str) -> str:
  if workflow_path == '-':
    workflow_json = sys.stdin.read()
  else:
    workflow_json = Path(workflow_path).read_text()
  return workflow_json


async def GetRemote(*, comfy_api_url: str):
  # Utility to help download/upload files.
  remote = GenericRemoteFileAPI()
  # This maps comfy+http://comfy_host:port/folder_type/subfolder/filename to
  # the /view and /upload API endpoints.
  remote.Register(
      ComfySchemeRemoteFileAPI(comfy_api_urls=[comfy_api_url], overwrite=True))
  # if args.comfy_install_file_url is not None:
  #   scheme = ToParseResult(args.comfy_install_file_url).scheme
  #   if scheme != 'file':
  #     raise ValueError(
  #         f'args.comfy_install_file_url must be a file:// URL, but is {args.comfy_install_file_url}'
  #     )

  #   # This one uses file:/// protocol on the local system. It is probably
  #   # faster. In the future, I hope to add other protocols, so this can be
  #   # used with other a choice remote storage systems as transparently as
  #   # possible.
  #   remote.Register(
  #       LocalRemoteFileAPI(upload_to_bases=[args.comfy_input_file_url],
  #                          download_from_bases=[
  #                              args.comfy_output_file_url,
  #                              args.comfy_temp_file_url
  #                          ]))
  return remote


async def DumpInfo(comfy_client: ComfyAPIClientBase,
                   catapult: ComfyCatapultBase, job_id: str, console: Console):

  status: JobStatus
  status, _ = await catapult.GetStatus(job_id=job_id)
  console.print(status.model_dump())

  system_stats: APISystemStats = await comfy_client.GetSystemStats()
  console.print('system_stats:', style='bold blue')
  console.print(YamlDump(system_stats.model_dump()))


async def StatusThread(stop_event: asyncio.Event,
                       comfy_client: ComfyAPIClientBase,
                       catapult: ComfyCatapultBase, job_id: str,
                       console: Console):
  while not stop_event.is_set():
    try:
      await asyncio.sleep(5)
      await DumpInfo(comfy_client=comfy_client,
                     catapult=catapult,
                     job_id=job_id,
                     console=console)
    except Exception as e:
      console.print(f'Error in StatusThread: {e}', style='bold red')
      console.print_exception()


def ParseArgs() -> Tuple[argparse.ArgumentParser, argparse.Namespace]:
  p = argparse.ArgumentParser(prog=_GetProgramName(),
                              description=__doc__,
                              formatter_class=_CustomRichHelpFormatter)
  p.add_argument('--version', action='version', version=_build_version)
  p.add_argument(
      '--comfy-api-url',
      type=str,
      default=None,
      help=
      'URL of the ComfyUI API. If left empty, will default to COMFY_API_URL.')
  p.add_argument('--debug-path',
                 type=Path,
                 default=Path('.debug'),
                 help='Path to save debug information.')

  # Add commands: execute, execute-bg, status, wait, cancel.

  sub_p = p.add_subparsers(dest='command',
                           title='commands',
                           description='Choose a command to run.',
                           required=True)

  p_execute = sub_p.add_parser('execute',
                               help='Execute a workflow.',
                               formatter_class=_CustomRichHelpFormatter)

  p_execute.add_argument('--job-id',
                         type=str,
                         default=None,
                         help='Unique job identifier.')
  p_execute.add_argument('--workflow-path',
                         type=str,
                         required=True,
                         help='Input markdown file, use "-" for stdin.')
  args = p.parse_args()
  return p, args


async def amain():
  console = Console(file=sys.stderr)
  args: Optional[argparse.Namespace] = None
  try:
    # Windows<10 requires this.
    colorama.init()

    p, args = ParseArgs()

    job_id: Optional[str] = args.job_id
    workflow_path: str = args.workflow_path
    comfy_api_url: Optional[str] = args.comfy_api_url
    debug_path: anyio.Path = anyio.Path(args.debug_path)

    if comfy_api_url is None:
      comfy_api_url = os.environ.get('COMFY_API_URL')
    if comfy_api_url is None or comfy_api_url == '':
      p.error(
          'comfy-api-url is required, or set the COMFY_API_URL environment variable.'
      )
      return

    workflow_template_json_str: str = await GetWorkflow(
        workflow_path=workflow_path)
    workflow_template_dict: dict = json.loads(workflow_template_json_str)

    async with ComfyAPIClient(comfy_api_url=comfy_api_url) as comfy_client:

      remote = await GetRemote(comfy_api_url=comfy_api_url)

      # Dump the ComfyUI server stats.
      system_stats: APISystemStats = await comfy_client.GetSystemStats()
      console.print('system_stats:', style='bold blue')
      console.print(YamlDump(system_stats.model_dump()))

      async with ComfyCatapult(comfy_client=comfy_client,
                               debug_path=debug_path / 'catapult',
                               debug_save_all=True) as catapult:

        dt_str = datetime.now(tz=timezone.utc).isoformat()

        if job_id is None:
          job_id = f'{slugify(dt_str)}-my-job-{uuid.uuid4()}'

        job_info = GenericWorkflowInfo(
            client=comfy_client,
            catapult=catapult,
            remote=remote,
            workflow_template_dict=workflow_template_dict,
            workflow_dict=json.loads(workflow_template_json_str),
            important=[],
            job_id=job_id,
            job_history_dict=None,
            comfy_api_url=comfy_api_url)

        stop_event = asyncio.Event()
        status_thread_future = asyncio.create_task(
            StatusThread(stop_event=stop_event,
                         comfy_client=comfy_client,
                         catapult=catapult,
                         job_id=job_id,
                         console=console))

        await RunWorkflow(job_info=job_info)
        stop_event.set()
        await status_thread_future

        console.print('Job complete, now dumping info', style='bold green')

        await DumpInfo(comfy_client=comfy_client,
                       catapult=catapult,
                       job_id=job_id,
                       console=console)

        console.print('All done', style='bold green')

  except Exception:
    console.print_exception()
    if args:
      console.print('args:', args._get_kwargs(), style='bold red')

    sys.exit(1)
    return


@dataclass
class GenericWorkflowInfo:
  client: ComfyAPIClient
  catapult: ComfyCatapult
  remote: GenericRemoteFileAPI
  workflow_template_dict: dict
  workflow_dict: dict
  important: list
  job_id: str
  job_history_dict: Optional[dict]
  comfy_api_url: str


async def PrepareWorkflow(*, job_info: GenericWorkflowInfo):
  # You have to write this function, to change the workflow_dict as you like.
  pass


async def DownloadResults(*, job_info: GenericWorkflowInfo):
  # You have to write this function, to download the results you care about.
  pass


async def RunWorkflow(*, job_info: GenericWorkflowInfo):

  # You have to write this function, to change the workflow_dict as you like.
  await PrepareWorkflow(job_info=job_info)

  job_id: str = job_info.job_id
  workflow_dict: dict = job_info.workflow_dict
  important: List[APINodeID] = job_info.important

  # Here the magic happens, the job is submitted to the ComfyUI server.
  job_info.job_history_dict = await job_info.catapult.Catapult(
      job_id=job_id, prepared_workflow=workflow_dict, important=important)

  # Now that the job is done, you have to write something that will go and get
  # the results you care about, if necessary.
  await DownloadResults(job_info=job_info)


def main():
  asyncio.run(amain())


if __name__ == '__main__':
  main()
