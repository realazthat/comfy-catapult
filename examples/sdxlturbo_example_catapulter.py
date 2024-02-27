# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT
#
# The Comfy Catapult project requires contributions made to this file be licensed
# under the MIT license or a compatible open source license. See LICENSE.md for
# the license text.

import asyncio
import copy
import json
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime
from pprint import pprint
from typing import List

from anyio import Path
from slugify import slugify

from comfy_catapult.api_client import ComfyAPIClient, ComfyAPIClientBase
from comfy_catapult.catapult import ComfyCatapult
from comfy_catapult.catapult_base import ComfyCatapultBase
from comfy_catapult.comfy_schema import (APIHistoryEntry, APINodeID,
                                         APIObjectInfo, APIObjectInputTuple,
                                         APISystemStats, APIWorkflow,
                                         APIWorkflowInConnection)
from comfy_catapult.comfy_utils import (DownloadPreviewImage, GetNodeByTitle,
                                        YamlDump)
from comfy_catapult.remote_file_api_base import RemoteFileAPIBase
from comfy_catapult.remote_file_api_comfy import ComfySchemeRemoteFileAPI
from comfy_catapult.remote_file_api_generic import GenericRemoteFileAPI
from comfy_catapult.remote_file_api_local import LocalRemoteFileAPI
from comfy_catapult.url_utils import ToParseResult
from examples.utilities.sdxlturbo_parse_args import ParseArgs


@dataclass
class ExampleWorkflowInfo:
  # Direct wrapper around the ComfyUI API.
  client: ComfyAPIClientBase
  # Job scheduler (the main point of this library).
  catapult: ComfyCatapultBase
  # Something to help with retrieving files from the ComfyUI storage.
  remote: RemoteFileAPIBase
  comfy_api_url: str

  # This should be the workflow json as a dict.
  workflow_template_dict: dict
  # This should begin as a deep copy of the template.
  workflow_dict: dict
  # This will hold the node ids that we must have results for.
  important: List[APINodeID]

  # Make this any string unique to this job.
  job_id: str

  # When the job is complete, this will be the `/history` json/dictionary for
  # this job.
  job_history_dict: dict | None

  # These are inputs that modify this particular workflow.
  ckpt_name: str | None
  positive_prompt: str
  negative_prompt: str
  # For this particular workflow, this will define the path to the output image.
  output_path: Path


async def RunExampleWorkflow(*, job_info: ExampleWorkflowInfo):

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


async def amain():
  args = await ParseArgs()

  print('args:', file=sys.stderr)
  pprint(args._asdict(),
         stream=sys.stderr,
         indent=2,
         width=120,
         sort_dicts=False)

  # Start a ComfyUI Client (provided in comfy_catapult.api_client).
  async with ComfyAPIClient(comfy_api_url=args.comfy_api_url) as comfy_client:

    # Utility to help download/upload files.
    remote = GenericRemoteFileAPI()
    # This maps comfy+http://comfy_host:port/folder_type/subfolder/filename to
    # the /view and /upload API endpoints.
    remote.Register(
        ComfySchemeRemoteFileAPI(comfy_api_urls=[args.comfy_api_url],
                                 overwrite=True))
    if args.comfy_install_file_url is not None:
      scheme = ToParseResult(args.comfy_install_file_url).scheme
      if scheme != 'file':
        raise ValueError(
            f'args.comfy_install_file_url must be a file:// URL, but is {args.comfy_install_file_url}'
        )

      # This one uses file:/// protocol on the local system. It is probably
      # faster. In the future, I hope to add other protocols, so this can be
      # used with other a choice remote storage systems as transparently as
      # possible.
      remote.Register(
          LocalRemoteFileAPI(upload_to_bases=[args.comfy_input_file_url],
                             download_from_bases=[
                                 args.comfy_output_file_url,
                                 args.comfy_temp_file_url
                             ]))

    # Dump the ComfyUI server stats.
    system_stats: APISystemStats = await comfy_client.GetSystemStats()
    print('system_stats:', file=sys.stderr)
    print(YamlDump(system_stats.model_dump()), file=sys.stderr)

    async with ComfyCatapult(comfy_client=comfy_client,
                             debug_path=args.debug_path,
                             debug_save_all=True) as catapult:

      dt_str = datetime.now().isoformat()

      # Read the workflow into a string.
      workflow_template_json_str: str = await args.api_workflow_json_path.read_text(
      )
      workflow_template_dict = json.loads(workflow_template_json_str)
      workflow_dict = copy.deepcopy(workflow_template_dict)

      job_info = ExampleWorkflowInfo(
          client=comfy_client,
          catapult=catapult,
          remote=remote,
          workflow_template_dict=workflow_template_dict,
          workflow_dict=workflow_dict,
          important=[],
          job_id=f'{slugify(dt_str)}-my-job-{uuid.uuid4()}',
          job_history_dict=None,
          comfy_api_url=args.comfy_api_url,
          ckpt_name=args.ckpt_name,
          positive_prompt=args.positive_prompt,
          negative_prompt=args.negative_prompt,
          output_path=args.output_path)
      await RunExampleWorkflow(job_info=job_info)


async def PrepareWorkflow(*, job_info: ExampleWorkflowInfo):
  # Connect the inputs to `workflow_dict` here.

  # Use the pydantic model to manipulate the workflow json.
  workflow = APIWorkflow.model_validate(job_info.workflow_dict)

  ##############################################################################
  # Get all the nodes we care about, by title.

  _, load_checkpoint = GetNodeByTitle(workflow=workflow,
                                      title='Load Checkpoint')

  # Unfortunately, two nodes 'CLIP Text Encode (Prompt)' are same title.
  # So instead, we'll find 'SamplerCustom' and work backwards.
  _, sampler_custom = GetNodeByTitle(workflow=workflow, title='SamplerCustom')

  in_conn = sampler_custom.inputs['positive']
  if not isinstance(in_conn, APIWorkflowInConnection):
    raise ValueError(
        f'Expected APIWorkflowInConnection, but got {type(in_conn)}')
  positive_prompt_id = in_conn.output_node_id
  positive_prompt = workflow.root[positive_prompt_id]

  in_conn = sampler_custom.inputs['negative']
  if not isinstance(in_conn, APIWorkflowInConnection):
    raise ValueError(
        f'Expected APIWorkflowInConnection, but got {type(in_conn)}')
  negative_prompt_id = in_conn.output_node_id
  negative_prompt = workflow.root[negative_prompt_id]

  preview_image_id, _ = GetNodeByTitle(workflow=workflow, title='Preview Image')
  ############################################################################

  # Get the /object_info, because we sometimes need to correct the model name,
  # because the model name is inconsistent between windows and linux if it is in
  # a directory, depending on the ComfyUI's system. E.g 'sd_xl_turbo_1.0_fp16'
  # vs 'SDXL-TURBO\sd_xl_turbo_1.0_fp16.safetensors' vs
  # 'SDXL-TURBO/sd_xl_turbo_1.0_fp16.safetensors'.
  object_info: APIObjectInfo = await job_info.client.GetObjectInfo()

  object_info_entry = object_info.root[load_checkpoint.class_type]

  if not isinstance(object_info_entry.input.required, dict):
    raise ValueError(
        f'Expected object_info_entry.input.required to be dict, but got {type(object_info_entry.input.required)}'
    )
  # Inputs are stored as a list/tuple of two things: the type (usually a string)
  # and a dictionary like {default: ..., min: ..., max: ...}.
  chpt_name_entry = object_info_entry.input.required['ckpt_name']
  if not isinstance(chpt_name_entry, APIObjectInputTuple):
    raise ValueError(
        f'Expected chpt_name_entry to be APIObjectInputTuple, but got {type(chpt_name_entry)}'
    )

  # Combo type is a weird type that isn't a string, but rather a list of actual
  # values that are valid to choose from, usually strings.
  if not isinstance(chpt_name_entry.type, list):
    raise ValueError(
        f'Expected chpt_name_entry.type to be list, but got {type(chpt_name_entry.type)}'
    )

  load_checkpoint_valid_models = []
  for item in chpt_name_entry.type:
    if not isinstance(item, str):
      raise ValueError(f'Expected item to be str, but got {type(item)}: {item}')
    load_checkpoint_valid_models.append(item)
  ############################################################################
  # Set some stuff in the workflow api json.

  if not ('sd_xl_turbo_1.0_fp16.safetensors'
          == load_checkpoint.inputs['ckpt_name']):
    raise ValueError(
        'sanity check, this is just what is in the workflow already.')

  if job_info.ckpt_name is not None:
    if job_info.ckpt_name not in load_checkpoint_valid_models:
      raise ValueError(
          f'ckpt_name must be one of {load_checkpoint_valid_models}, but is {job_info.ckpt_name}'
      )
    load_checkpoint.inputs['ckpt_name'] = job_info.ckpt_name

  positive_prompt.inputs['text'] = job_info.positive_prompt
  negative_prompt.inputs['text'] = job_info.negative_prompt
  ############################################################################
  # Mark some nodes as required to be executed, in order for us to consider
  # the job done.
  job_info.important.append(preview_image_id)
  ############################################################################
  # Save our changes to the job_info workflow.
  job_info.workflow_dict = workflow.model_dump()


async def DownloadResults(*, job_info: ExampleWorkflowInfo):
  print('job_history:', file=sys.stderr)
  if job_info.job_history_dict is None:
    raise AssertionError('job_info.job_history_dict is None')
  job_history = APIHistoryEntry.model_validate(job_info.job_history_dict)
  workflow = APIWorkflow.model_validate(job_info.workflow_dict)
  print(YamlDump(job_history.model_dump()), file=sys.stderr)

  preview_image_id, _ = GetNodeByTitle(workflow=workflow, title='Preview Image')

  # You are gonna want to look at how this function works.
  await DownloadPreviewImage(node_id=preview_image_id,
                             job_history=job_history,
                             field_path='images[0]',
                             comfy_api_url=job_info.comfy_api_url,
                             remote=job_info.remote,
                             local_dst_path=Path(job_info.output_path))


asyncio.run(amain(), debug=True)
