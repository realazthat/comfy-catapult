# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT
#
# The Comfy Catapult project requires contributions made to this file be licensed
# under the MIT license or a compatible open source license. See LICENSE.md for
# the license text.

import logging
from typing import (Generator, Hashable, List, Literal, NamedTuple, Optional,
                    Union, cast)

import pydash
from anyio import Path

from .comfy_schema import (APIHistoryEntry, APINodeID, APIOutputUI,
                           APIWorkflow, APIWorkflowNodeInfo,
                           ComfyUIPathTriplet)
from .errors import MultipleNodesFound, NodeNotFound
from .remote_file_api_base import RemoteFileAPIBase

logger = logging.getLogger(__name__)


class NodeIDAndNode(NamedTuple):
  node_id: APINodeID
  node_info: APIWorkflowNodeInfo


def FindNodesByTitle(*, workflow: APIWorkflow,
                     title: str) -> Generator[NodeIDAndNode, None, None]:
  node_id: APINodeID
  node_info: APIWorkflowNodeInfo
  for node_id, node_info in workflow.root.items():
    if node_info.meta is not None and node_info.meta.title == title:
      yield NodeIDAndNode(node_id=node_id, node_info=node_info)


def FindNodeByTitle(*, workflow: APIWorkflow,
                    title: str) -> Optional[NodeIDAndNode]:
  for (node_id, node_info) in FindNodesByTitle(workflow=workflow, title=title):
    return NodeIDAndNode(node_id=node_id, node_info=node_info)
  return None


def GetNodeByTitle(*, workflow: APIWorkflow, title: str) -> NodeIDAndNode:
  nodes: List[NodeIDAndNode] = list(
      FindNodesByTitle(workflow=workflow, title=title))

  if len(nodes) == 0:
    raise NodeNotFound(title=title, node_id=None)

  if len(nodes) > 1:
    raise MultipleNodesFound(search_titles=[title],
                             search_nodes=[title],
                             found_titles=[],
                             found_nodes=[node_id for node_id, _ in nodes])
  node_id, node_info = nodes[0]

  return NodeIDAndNode(node_id=node_id, node_info=node_info)


def FindNode(*, workflow: APIWorkflow,
             id_or_title: Union[int, str]) -> Optional[NodeIDAndNode]:
  id_node_id: Optional[APINodeID] = None
  # id_node_error: Optional[Exception] = None

  title_node_id: Optional[APINodeID] = None
  # title_node_error: Optional[Exception] = None

  try:
    if isinstance(id_or_title, str):
      title_node_id, _ = GetNodeByTitle(workflow=workflow, title=id_or_title)

  except NodeNotFound:
    # id_node_error = e
    pass

  id_or_title_str = str(id_or_title)
  try:
    id_node_id_: APINodeID = cast(APINodeID, id_or_title_str)
    if id_node_id_ in workflow.root:
      id_node_id = id_node_id_
  except ValueError:
    # title_node_error = e
    pass

  if title_node_id is None and id_node_id is None:
    return None
  elif title_node_id is not None and id_node_id is not None:
    raise MultipleNodesFound(search_titles=[id_or_title_str],
                             search_nodes=[id_node_id],
                             found_titles=[title_node_id],
                             found_nodes=[id_node_id])
  elif title_node_id is not None:
    return NodeIDAndNode(node_id=title_node_id,
                         node_info=workflow.root[title_node_id])
  else:
    if id_node_id is None:
      raise AssertionError('id_node_id is None')

    return NodeIDAndNode(node_id=id_node_id,
                         node_info=workflow.root[id_node_id])


def GetNode(*, workflow: APIWorkflow, id_or_title: Union[str,
                                                         int]) -> NodeIDAndNode:
  node = FindNode(workflow=workflow, id_or_title=id_or_title)
  if node is None:
    raise NodeNotFound(title=id_or_title, node_id=id_or_title)
  return node


def GenerateNewNodeID(*, workflow: APIWorkflow) -> APINodeID:
  all_keys = workflow.root.keys()
  max_integer = 0

  # Filter all keys that fail to convert to int
  for key in all_keys:
    try:
      max_integer = max(int(key), max_integer)
    except ValueError:
      continue

  return cast(APINodeID, str(max_integer + 1))


async def DownloadPreviewImage(*, node_id: APINodeID,
                               job_history: APIHistoryEntry,
                               field_path: Union[Hashable, List[Hashable]],
                               comfy_api_url: str, remote: RemoteFileAPIBase,
                               local_dst_path: Path):
  """Downloads something that looks like an Preview Image node's outputs.

  * field_path=='gifs[0]' works for Video Combine
  * field_path=='images[0]' works for Preview Image



  Example Preview Image Workflow API json:

  ```
  '25':
    inputs:
      images:
      - '8'
      - 0
    class_type: PreviewImage
    meta:
      title: Preview Image
  ```

  Example Preview Image node output:

  ```
  outputs:
    '25':
      images:
      - filename: ComfyUI_temp_huntb_00001_.png
        subfolder: ''
        type: temp
  ```

  Example Video Combine node output:

  TODO: Put an example here.

  Args:
      node_id: The node_id.
      job_history: The job_history.
      field_path: A pydash field path, for the pydash.get() and pydash.set_()
        functions.
      comfy_api_url: e.g http://127.0.0.1:8188.
      remote: A RemoteFileAPI instance.
      local_dst_path: Path to the local destination file.
  """

  if job_history.outputs is None:
    raise AssertionError('job_history.outputs is None')

  if node_id not in job_history.outputs:
    raise Exception(f'{node_id} not in job_history.outputs')

  node_outputs: APIOutputUI = job_history.outputs[node_id]

  file_dict: dict = pydash.get(node_outputs.root, field_path)

  if 'filename' not in file_dict:
    raise Exception(f'Expected "filename" in {file_dict}')
  filename: str = file_dict['filename']
  if not isinstance(filename, str):
    raise Exception(f'Expected "filename" to be str, got {type(filename)}')
  if 'subfolder' not in file_dict:
    raise Exception(f'Expected "subfolder" in {file_dict}')
  subfolder: str = file_dict['subfolder']
  if not isinstance(subfolder, str):
    raise Exception(f'Expected "subfolder" to be str, got {type(subfolder)}')
  if 'type' not in file_dict:
    raise Exception(f'Expected "type" in {file_dict}')
  folder_type: Literal['temp', 'output'] = file_dict['type']
  if not isinstance(folder_type, str):
    raise Exception(f'Expected "type" to be str, got {type(folder_type)}')
  if folder_type not in ['temp', 'output']:
    raise Exception(
        f'Expected "type" to be "temp" or "output", got {folder_type}')

  triplet = ComfyUIPathTriplet(type=folder_type,
                               subfolder=subfolder,
                               filename=filename)
  return await remote.DownloadTriplet(untrusted_comfy_api_url=comfy_api_url,
                                      untrusted_src_triplet=triplet,
                                      dst_path=local_dst_path)
