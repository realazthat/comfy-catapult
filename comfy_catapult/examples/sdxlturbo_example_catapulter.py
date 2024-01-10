# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT
#
# The Comfy Catapult project require contributions made to this file be licensed
# under the MIT license or a compatible open source license. See LICENSE.md for
# the license text.

import asyncio
import sys
import uuid
from pprint import pprint
from typing import List

from comfy_catapult.api_client import ComfyAPIClient, ComfyAPIClientBase
from comfy_catapult.catapult import ComfyCatapult, JobStatus
from comfy_catapult.comfy_config import RemoteComfyConfig
from comfy_catapult.comfy_schema import (APIHistoryEntry, APIObjectInfo,
                                         APIObjectInputTuple, APISystemStats,
                                         APIWorkflow, APIWorkflowInConnection,
                                         NodeID)
from comfy_catapult.comfy_utils import (DownloadPreviewImage, GetNodeByTitle,
                                        YamlDump)
from comfy_catapult.examples.utilities.sdxlturbo_parse_args import (Args,
                                                                    ParseArgs)
from comfy_catapult.remote_file_api_base import RemoteFileAPIBase
from comfy_catapult.remote_file_api_comfy import ComfySchemeRemoteFileAPI
from comfy_catapult.remote_file_api_generic import GenericRemoteFileAPI
from comfy_catapult.remote_file_api_local import LocalRemoteFileAPI
from comfy_catapult.url_utils import ToParseResult


async def amain():
  args = await ParseArgs()

  print('args:', file=sys.stderr)
  pprint(args._asdict(),
         stream=sys.stderr,
         indent=2,
         width=120,
         sort_dicts=False)
  comfy_api_url = args.comfy_api_url

  # These are used to insure that files are not written/read outside of the
  # comfy_input_url and comfy_output_url directories.
  comfy_config = RemoteComfyConfig(
      comfy_api_url=args.comfy_api_url,
      base_file_url=args.comfy_base_file_url,
      input_file_url=args.comfy_input_file_url,
      temp_file_url=args.comfy_temp_file_url,
      output_file_url=args.comfy_output_file_url,
  )

  # Read the workflow into a string.
  workflow_json_str: str = await args.api_workflow_json_path.read_text()

  # Parse it with the pydantic model so we can manipulate it more nicely than
  # with raw json, we'll use this as a template, and fill in the inputs to
  # customize it for this job.
  #
  # If you prefer, you can work with raw python dict conversion of the json.
  workflow: APIWorkflow
  workflow = APIWorkflow.model_validate_json(workflow_json_str)

  # Start a ComfyUI Client (provided in comfy_catapult.api_client).
  async with ComfyAPIClient(comfy_api_url=args.comfy_api_url) as comfy_client:

    # Utility to help download/upload files.
    remote = GenericRemoteFileAPI()
    # This maps comfy+http://comfy_host:port/folder_type/subfolder/filename to
    # the /view and /upload API endpoints.
    remote.Register(
        ComfySchemeRemoteFileAPI(comfy_api_urls=[comfy_config.comfy_api_url],
                                 overwrite=True))
    if comfy_config.base_file_url is not None:
      assert ToParseResult(comfy_config.base_file_url).scheme == 'file'

      # This one uses file:/// protocol on the local system. It is probably
      # faster. In the future, I hope to add other protocols, so this can be
      # used with other a choice remote storage systems as transparently as
      # possible.
      remote.Register(
          LocalRemoteFileAPI(upload_to_bases=[comfy_config.input_file_url],
                             download_from_bases=[
                                 comfy_config.output_file_url,
                                 comfy_config.temp_file_url
                             ]))

    # Now specialize the workflow for this job.
    important: List[NodeID] = []
    await PrepareWorkflow(client=comfy_client,
                          workflow=workflow,
                          args=args,
                          important=important)

    # Dump the ComfyUI server stats.
    system_stats: APISystemStats = await comfy_client.GetSystemStats()
    print('system_stats:', file=sys.stderr)
    print(YamlDump(system_stats.model_dump()), file=sys.stderr)

    async with ComfyCatapult(comfy_client=comfy_client,
                             debug_path=args.debug_path) as catapult:
      job_id = str(uuid.uuid4())

      # Launch the job.
      job_history_dict: dict = await catapult.Catapult(
          job_id=job_id,
          prepared_workflow=workflow.model_dump(),
          important=important)

      # Job is done.

      # Now, we can either trudge through job_history_dict, or we can convert it
      # to a pydantic model, which is easier to work with.
      job_history = APIHistoryEntry.model_validate(job_history_dict)

      status: JobStatus
      status, future = await catapult.GetStatus(job_id=job_id)
      print('status:', file=sys.stderr)
      print(YamlDump(status._asdict()), file=sys.stderr)
      print('job_history:', file=sys.stderr)
      print(YamlDump(job_history.model_dump()), file=sys.stderr)

      # Download Preview Image.
      await FinishWorkflow(comfy_api_url=comfy_api_url,
                           remote=remote,
                           workflow=workflow,
                           args=args,
                           job_history=job_history)


async def PrepareWorkflow(*, client: ComfyAPIClientBase, workflow: APIWorkflow,
                          args: Args, important: List[NodeID]):
  # Connect the inputs to `workflow` here.

  # Get nodes by title.

  _, load_checkpoint = GetNodeByTitle(workflow=workflow,
                                      title='Load Checkpoint')

  # Unfortunately, two nodes 'CLIP Text Encode (Prompt)' are same title.
  # So instead, we'll find 'SamplerCustom' and work backwards.
  _, sampler_custom = GetNodeByTitle(workflow=workflow, title='SamplerCustom')

  in_conn = sampler_custom.inputs['positive']
  assert isinstance(in_conn, APIWorkflowInConnection)
  positive_prompt_id = in_conn.output_node_id
  positive_prompt = workflow.root[positive_prompt_id]

  in_conn = sampler_custom.inputs['negative']
  assert isinstance(in_conn, APIWorkflowInConnection)
  negative_prompt_id = in_conn.output_node_id
  negative_prompt = workflow.root[negative_prompt_id]

  preview_image_id, _ = GetNodeByTitle(workflow=workflow, title='Preview Image')
  ############################################################################

  # Get the /object_info, because we sometimes need to correct the model name,
  # because the model name is inconsistent between windows and linux if it is in
  # a directory, depending on the ComfyUI's system. E.g 'sd_xl_turbo_1.0_fp16'
  # vs 'SDXL-TURBO\sd_xl_turbo_1.0_fp16.safetensors' vs
  # 'SDXL-TURBO/sd_xl_turbo_1.0_fp16.safetensors'.
  object_info: APIObjectInfo = await client.GetObjectInfo()

  object_info_entry = object_info.root[load_checkpoint.class_type]

  assert isinstance(object_info_entry.input.required, dict)
  # Inputs are stored as a list/tuple of two things: the type (usually a string)
  # and a dictionary like {default: ..., min: ..., max: ...}.
  chpt_name_entry = object_info_entry.input.required['ckpt_name']
  assert isinstance(chpt_name_entry, APIObjectInputTuple), type(chpt_name_entry)

  # Combo type is a weird type that isn't a string, but rather a list of actual
  # values that are valid to choose from, usually strings.
  assert isinstance(chpt_name_entry.type, list), type(chpt_name_entry.type)

  load_checkpoint_valid_models = []
  for item in chpt_name_entry.type:
    assert isinstance(item, str), (f'item must be str, but is {type(item)}')
    load_checkpoint_valid_models.append(item)
  ############################################################################
  # Set some stuff in the workflow api json.

  assert (
      'sd_xl_turbo_1.0_fp16.safetensors' == load_checkpoint.inputs['ckpt_name']
  ), ('sanity check, this is just what is in the workflow already.')

  if args.ckpt_name is not None:
    assert args.ckpt_name in load_checkpoint_valid_models, (
        f'ckpt_name must be one of {load_checkpoint_valid_models}, but is {args.ckpt_name}'
    )
    load_checkpoint.inputs['ckpt_name'] = args.ckpt_name

  positive_prompt.inputs['text'] = args.positive_prompt
  negative_prompt.inputs['text'] = args.negative_prompt
  negative_prompt.inputs['text'] = args.negative_prompt
  ############################################################################
  # Mark some nodes as required to be executed, in order for us to consider
  # the job done.
  important.append(preview_image_id)
  ############################################################################


async def FinishWorkflow(*, comfy_api_url: str, remote: RemoteFileAPIBase,
                         workflow: APIWorkflow, args: Args,
                         job_history: APIHistoryEntry):
  print('job_history:', file=sys.stderr)
  print(YamlDump(job_history.model_dump()), file=sys.stderr)

  preview_image_id, _ = GetNodeByTitle(workflow=workflow, title='Preview Image')

  # You are gonna want to look at how this function works.
  await DownloadPreviewImage(node_id=preview_image_id,
                             job_history=job_history,
                             field_path='images[0]',
                             comfy_api_url=comfy_api_url,
                             remote=remote,
                             local_dst_path=args.output_path)


asyncio.run(amain(), debug=True)
