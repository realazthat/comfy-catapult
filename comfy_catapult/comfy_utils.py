# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT
#
# The Comfy Catapult project requires contributions made to this file be licensed
# under the MIT license or a compatible open source license. See LICENSE.md for
# the license text.

import dataclasses
import datetime
import json
import logging
import textwrap
import traceback
from asyncio import CancelledError
from dataclasses import is_dataclass
from typing import (Any, Dict, Generator, Hashable, List, Literal, NamedTuple,
                    Optional, Type, TypeVar, Union, cast)

import aiofiles
import pydantic_core
import pydash
import yaml
from anyio import Path
from pydantic import BaseModel
from pydash import slugify

from .comfy_schema import (APIHistoryEntry, APINodeID, APIOutputUI,
                           APIWorkflow, APIWorkflowNodeInfo,
                           ComfyUIPathTriplet)
from .errors import MultipleNodesFound, NodeNotFound
from .remote_file_api_base import RemoteFileAPIBase

MAX_DUMP_LINES: Optional[int] = 200
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


class _CustomDumper(yaml.Dumper):

  def represent_tuple(self, data):
    return self.represent_list(data)


_CustomDumper.add_representer(tuple, _CustomDumper.represent_tuple)


def YamlDump(data: Any) -> str:
  return yaml.dump(data, indent=2, Dumper=_CustomDumper, sort_keys=False)


async def _GetNewPath(*, parent_path: Path) -> Path:
  now = datetime.datetime.now(datetime.timezone.utc)
  name = now.strftime('%Y-%m-%d_%H-%M-%S_%f')
  path = parent_path / name
  index = 1
  while await path.exists():
    path = parent_path / f'{name}_{index}'
    index += 1
  await path.mkdir(parents=True, exist_ok=True)
  return path


async def BigYamlDump(data: Any, *, max_lines: Optional[int],
                      path: Path) -> str:
  yaml_str = YamlDump(data)
  line_count = len(yaml_str.splitlines())
  if max_lines is None or line_count <= max_lines:
    return yaml_str

  await path.parent.mkdir(parents=True, exist_ok=True)
  async with aiofiles.open(path, 'w') as f:
    await f.write(yaml_str)
  return f'Too large, see {json.dumps(str(path))}'


async def BigErrorStrDump(exception: Exception, max_lines: Optional[int],
                          path: Path) -> str:
  if max_lines is None:
    return str(exception)
  error_str = str(exception)
  error_lines = error_str.splitlines()
  error_line = error_lines[0]

  await path.parent.mkdir(parents=True, exist_ok=True)

  async with aiofiles.open(path, 'w') as f:
    await f.write(error_str)
  return error_line + f' (Wrote full error_str to {json.dumps(str(path))})'


_BaseModelT = TypeVar('_BaseModelT', bound=BaseModel)


def _IsDataclassInstance(instance):
  return is_dataclass(instance) and not isinstance(instance, type)


class _ExtraFieldWarning(NamedTuple):
  path: List[Any]
  thing: Any
  message: str


def _WarnModelExtras(*, path: List[Any],
                     thing: Any) -> Generator[_ExtraFieldWarning, None, None]:
  if _IsDataclassInstance(thing):
    for field in dataclasses.fields(thing):
      item = getattr(thing, field.name)
      yield from _WarnModelExtras(path=path + [field.name], thing=item)
  elif isinstance(thing, (list, tuple)):
    for index, item in enumerate(thing):
      if isinstance(item, BaseModel):
        yield from _WarnModelExtras(path=path + [index], thing=item)
  elif isinstance(thing, (list, tuple)):
    for index, item in enumerate(thing):
      if isinstance(item, BaseModel):
        yield from _WarnModelExtras(path=path + [index], thing=item)
  elif isinstance(thing, dict):
    for key, item in thing.items():
      if isinstance(item, BaseModel):
        yield from _WarnModelExtras(path=path + [key], thing=item)
  elif isinstance(thing, BaseModel):
    if thing.model_extra is not None:

      for key, value in thing.model_extra.items():
        yield _ExtraFieldWarning(
            path=path + [key],
            thing=value,
            message=
            f'Warning: Unknown field: {key} in {thing.__class__.__name__} at {path}'
        )
        yield from _WarnModelExtras(path=path + [key], thing=value)

    for key, value in thing.model_fields.items():
      yield from _WarnModelExtras(path=path + [key], thing=value)
  else:
    pass


async def TryParseAsModel(
    *,
    content: Any,
    model_type: Type[_BaseModelT],
    errors_dump_directory: Optional[Path],
    strict: Literal['yes', 'no', 'warn'] = 'warn') -> _BaseModelT:

  async def _Internal(errors_dump_directory: Optional[Path]):
    error_dump_path: Optional[Path] = None

    try:
      try:
        return model_type.model_validate(content,
                                         strict=strict in ['yes', 'warn'])
      except pydantic_core.ValidationError as e:
        if strict == 'yes':
          # Go to the except below which just prints the error.
          raise
        # Try parsing it non-strictly, and then warn about the error if it
        # succeeds. If it errors, then we'll go to the except below which
        # prints the error.
        model = model_type.model_validate(content, strict=False)
        if error_dump_path is None and errors_dump_directory is not None:
          error_dump_path = await _GetNewPath(parent_path=errors_dump_directory)

        if error_dump_path is not None:
          error_line = await BigErrorStrDump(
              exception=e,
              max_lines=MAX_DUMP_LINES,
              path=error_dump_path /
              f'{slugify(str(model_type))}-error_str.txt')

          model_dump_yaml = await BigYamlDump(
              model.model_dump(),
              max_lines=MAX_DUMP_LINES,
              path=error_dump_path /
              f'{slugify(str(model_type))}-model_dump.yaml')
          input_content_yaml = await BigYamlDump(
              content,
              max_lines=MAX_DUMP_LINES,
              path=error_dump_path /
              f'{slugify(str(model_type))}-input_content.yaml')
        else:
          error_line = str(e)
          model_dump_yaml = YamlDump(model.model_dump())
          input_content_yaml = YamlDump(content)

        msg = f'Warning: Error parsing {model_type} with strict=True: {error_line}'
        logger.error(
            f'{msg}:'
            f'\n\n{textwrap.indent(str(e), prefix="  ")}'
            f'\nParsed Model:\n{textwrap.indent(model_dump_yaml, prefix="  ")}'
            f'\nInput content\n{textwrap.indent(input_content_yaml, prefix="  ")}'
            f'\n{msg}')
        return model
    except pydantic_core.ValidationError as e:
      # It failed strictly or non-strictly. Print the error and raise.

      if error_dump_path is None and errors_dump_directory is not None:
        error_dump_path = await _GetNewPath(parent_path=errors_dump_directory)

      if error_dump_path is not None:
        error_line = await BigErrorStrDump(
            exception=e,
            max_lines=MAX_DUMP_LINES,
            path=error_dump_path / f'{slugify(str(model_type))}-error_str.txt')
      else:
        error_line = str(e)
      msg_summary = f'Error parsing {model_type}: {error_line}'
      msg = f'{msg_summary}'
      if error_dump_path is not None:
        input_content_yaml = await BigYamlDump(
            content,
            max_lines=MAX_DUMP_LINES,
            path=error_dump_path /
            f'{slugify(str(model_type))}-input_content.yaml')
        msg += '\nInput content\n' + textwrap.indent(input_content_yaml,
                                                     prefix='  ')
        errors_yaml = await BigYamlDump(
            e.errors(),
            max_lines=MAX_DUMP_LINES,
            path=error_dump_path / f'{slugify(str(model_type))}-errors.yaml')
        msg += '\nError details\n' + textwrap.indent(errors_yaml, prefix='  ')
      else:
        msg += '\nInput content\n' + textwrap.indent(YamlDump(content),
                                                     prefix='  ')
        msg += '\nError details\n' + textwrap.indent(YamlDump(e.errors()),
                                                     prefix='  ')

      msg += f'\n{msg_summary}'
      raise Exception(msg) from e

  model = await _Internal(errors_dump_directory=errors_dump_directory)
  extra_fields_warnings = _WarnModelExtras(path=[], thing=model)
  if strict == 'warn':
    for warning in extra_fields_warnings:
      logger.warn(warning.message)
  elif strict == 'yes':
    for warning in extra_fields_warnings:
      raise Exception(warning.message)

  # TODO: Renable this or remove it.
  # model_dump: Dict[str, Any] = model.model_dump()
  # differences = list(diff(model_dump, content))
  # if len(differences) > 0:
  #   print('Warning: Model parsed with differences from the content', file=sys.stderr)
  #   print('content:', file=sys.stderr)
  #   print(textwrap.indent(_YamlDump(content), prefix='  '), file=sys.stderr)
  #   print('model_dump:', file=sys.stderr)
  #   print(textwrap.indent(_YamlDump(model_dump), prefix='  '), file=sys.stderr)
  #   print('differences:', file=sys.stderr)
  #   print(textwrap.indent(_YamlDump(differences), prefix='  '), file=sys.stderr)
  return model


class WatchVar:

  def __init__(self, **kwargs):
    self._kwargs = kwargs

  def __enter__(self):
    pass

  def __exit__(self, exc_type, exc, tb):
    if exc is not None:
      if isinstance(
          exc, (KeyboardInterrupt, SystemExit, CancelledError, BaseException)):
        return

      extra: Dict[str, Any] = {}
      if exc_type is not None:
        extra['exc_type'] = type(exc_type).__name__
      extra['kwargs'] = self._kwargs
      extra['tb'] = traceback.format_tb(tb)

      logger.error(
          f'{type(self).__name__}: Error occurred: {json.dumps(str(exc))} ({type(exc).__name__})'
          f'\nTraceback:\n{textwrap.indent("".join(traceback.format_tb(tb)), "  ")}'
          f'\nYou are watching these variables:\n{textwrap.indent(YamlDump(self._kwargs), "  ")}',
          extra=extra)
