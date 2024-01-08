# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT
#
# The Catapult require contributions made to this file be licensed under the MIT
# license or a compatible open source license. See LICENSE.md for the license
# text.

import dataclasses
import datetime
import sys
import textwrap
from dataclasses import is_dataclass
from typing import (Any, Generator, Hashable, List, Literal, NamedTuple, Type,
                    TypeVar)

import aiofiles
import pydantic_core
import pydash
import yaml
from anyio import Path
from pydantic import BaseModel
from pydash import slugify

from comfy_catapult.comfy_schema import (APIHistoryEntry, APIOutputUI,
                                         APIWorkflow, APIWorkflowNodeInfo,
                                         NodeID)
from comfy_catapult.errors import MultipleNodesFound, NodeNotFound
from comfy_catapult.remote_file_api_base import RemoteFileAPIBase
from comfy_catapult.url_utils import ComfyUIPathTriplet

MAX_DUMP_LINES: int | None = 200
DUMP_DIR: Path = Path('.logs/dumps')


class NodeIDAndNode(NamedTuple):
  node_id: NodeID
  node_info: APIWorkflowNodeInfo


def FindNodesByTitle(*, workflow: APIWorkflow,
                     title: str) -> Generator[NodeIDAndNode, None, None]:
  node_id: NodeID
  node_info: APIWorkflowNodeInfo
  for node_id, node_info in workflow.root.items():
    if node_info.meta is not None and node_info.meta.title == title:
      yield NodeIDAndNode(node_id=node_id, node_info=node_info)


def FindNodeByTitle(*, workflow: APIWorkflow,
                    title: str) -> NodeIDAndNode | None:
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
             id_or_title: str) -> NodeIDAndNode | None:
  id_node_id: NodeID | None = None
  # id_node_error: Exception | None = None

  title_node_id: NodeID | None = None
  # title_node_error: Exception | None = None

  try:
    title_node_id, _ = GetNodeByTitle(workflow=workflow, title=id_or_title)

  except NodeNotFound:
    # id_node_error = e
    pass

  try:
    id_node_id = NodeID(id_or_title)
    # node = workflow.root[id_node_id]
  except ValueError:
    # title_node_error = e
    pass

  if title_node_id is None and id_node_id is None:
    return None
  elif title_node_id is not None and id_node_id is not None:
    raise MultipleNodesFound(search_titles=[id_or_title],
                             search_nodes=[id_node_id],
                             found_titles=[id_or_title],
                             found_nodes=[id_node_id])
  elif title_node_id is not None:
    return NodeIDAndNode(node_id=title_node_id,
                         node_info=workflow.root[title_node_id])
  else:
    assert id_node_id is not None
    return NodeIDAndNode(node_id=id_node_id,
                         node_info=workflow.root[id_node_id])


def GetNode(*, workflow: APIWorkflow, id_or_title: str) -> NodeIDAndNode:
  node = FindNode(workflow=workflow, id_or_title=id_or_title)
  if node is None:
    raise NodeNotFound(title=id_or_title, node_id=id_or_title)
  return node


def GenerateNewNodeID(*, workflow: APIWorkflow) -> NodeID:
  all_keys = workflow.root.keys()
  max_integer = 0

  # Filter all keys that fail to convert to int
  for key in all_keys:
    try:
      max_integer = max(int(key), max_integer)
    except ValueError:
      continue

  return NodeID(str(max_integer + 1))


async def DownloadPreviewImage(*, node_id: NodeID, job_history: APIHistoryEntry,
                               field_path: Hashable | List[Hashable],
                               comfy_api_url: str, remote: RemoteFileAPIBase,
                               local_dst_path: Path):
  """Downloads something that looks like an Preview Image node's outputs.

  * field_path=='gifs[0]' works for Video Combine
  * field_path=='images[0]' works for Preview Image

  Args:
      node_id: The node_id.
      job_history: The job_history.
      field_path: A pydash field path, for the pydash.get() and pydash.set_()
        functions.
      comfy_api_url: e.g http://127.0.0.1:8188.
      remote: A RemoteFileAPI instance.
      local_dst_path: Path to the local destination file.
  """

  # Example Preview Image node output:
  #
  # TODO: Put an example here.

  # Example Video Combine node output:
  #
  # TODO: Put an example here.

  assert job_history.outputs is not None

  if node_id not in job_history.outputs:
    raise Exception(f'{node_id} not in job_history.outputs')

  node_outputs: APIOutputUI = job_history.outputs[node_id]

  file_dict: dict = pydash.get(node_outputs.root, field_path)

  assert 'filename' in file_dict, f'Expected "filename" in {file_dict}'
  filename: str = file_dict['filename']
  assert isinstance(filename, str)
  assert 'subfolder' in file_dict, f'Expected "subfolder" in {file_dict}'
  subfolder: str = file_dict['subfolder']
  assert isinstance(subfolder, str)
  assert 'type' in file_dict, f'Expected "type" in {file_dict}'
  folder_type: Literal['temp', 'output'] = file_dict['type']
  assert isinstance(folder_type, str)
  assert folder_type in ['temp', 'output']

  triplet = ComfyUIPathTriplet(comfy_api_url=comfy_api_url,
                               folder_type=folder_type,
                               subfolder=subfolder,
                               filename=filename)
  return await remote.DownloadTriplet(untrusted_src_triplet=triplet,
                                      dst_path=local_dst_path)


class _CustomDumper(yaml.Dumper):

  def represent_tuple(self, data):
    return self.represent_list(data)


_CustomDumper.add_representer(tuple, _CustomDumper.represent_tuple)


def YamlDump(data: Any) -> str:
  return yaml.dump(data, indent=2, Dumper=_CustomDumper, sort_keys=False)


async def _GetNewPath(*, parent_path: Path) -> Path:
  name = datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S_%f')
  path = parent_path / name
  index = 1
  while await path.exists():
    path = parent_path / f'{name}_{index}'
    index += 1
  return path


async def BigYamlDump(data: Any, *, max_lines: int | None, path: Path) -> str:
  yaml_str = YamlDump(data)
  line_count = len(yaml_str.splitlines())
  if max_lines is None or line_count <= max_lines:
    return yaml_str

  await path.parent.mkdir(parents=True, exist_ok=True)
  async with aiofiles.open(path, 'w') as f:
    await f.write(yaml_str)
  return f'Too large, see {repr(str(path))}'


async def BigErrorStrDump(exception: Exception, max_lines: int | None,
                          path: Path) -> str:
  if max_lines is None:
    return str(exception)
  error_str = str(exception)
  error_lines = error_str.splitlines()
  error_line = error_lines[0]

  await path.parent.mkdir(parents=True, exist_ok=True)

  async with aiofiles.open(path, 'w') as f:
    await f.write(error_str)
  return error_line + f' (Wrote full error_str to {repr(str(path))})'


_BaseModelT = TypeVar('_BaseModelT', bound=BaseModel)


def _IsDataclassInstance(instance):
  return is_dataclass(instance) and not isinstance(instance, type)


def _IsNamedTuple(instance):
  return isinstance(instance, tuple) and hasattr(instance, '_fields')


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
    strict: Literal['yes', 'no', 'warn'] = 'warn') -> _BaseModelT:

  async def _Internal():
    dump_path: Path | None = None

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
        if dump_path is None:
          dump_path = await _GetNewPath(parent_path=DUMP_DIR)

        error_line = await BigErrorStrDump(
            exception=e,
            max_lines=MAX_DUMP_LINES,
            path=dump_path / f'{slugify(str(model_type))}-error_str.txt')

        model_dump_yaml = await BigYamlDump(
            model.model_dump(),
            max_lines=MAX_DUMP_LINES,
            path=dump_path / f'{slugify(str(model_type))}-model_dump.yaml')
        input_content_yaml = await BigYamlDump(
            content,
            max_lines=MAX_DUMP_LINES,
            path=dump_path / f'{slugify(str(model_type))}-input_content.yaml')
        msg = f'Warning: Error parsing {model_type} with strict=True: {error_line}'
        print(
            f'{msg}:'
            f'\n\n{textwrap.indent(str(e), prefix="  ")}'
            f'\nParsed Model:\n{textwrap.indent(model_dump_yaml, prefix="  ")}'
            f'\nInput content\n{textwrap.indent(input_content_yaml, prefix="  ")}'
            f'\n{msg}',
            file=sys.stderr)
        return model
    except pydantic_core.ValidationError as e:
      # It failed strictly or non-strictly. Print the error and raise.

      if dump_path is None:
        dump_path = await _GetNewPath(parent_path=DUMP_DIR)
        await dump_path.mkdir(parents=True, exist_ok=True)

      error_line = await BigErrorStrDump(
          exception=e,
          max_lines=MAX_DUMP_LINES,
          path=dump_path / f'{slugify(str(model_type))}-error_str.txt')
      msg = f'Error parsing {model_type}: {error_line}'

      input_content_yaml = await BigYamlDump(
          content,
          max_lines=MAX_DUMP_LINES,
          path=dump_path / f'{slugify(str(model_type))}-input_content.yaml')
      errors_yaml = await BigYamlDump(e.errors(),
                                      max_lines=MAX_DUMP_LINES,
                                      path=dump_path /
                                      f'{slugify(str(model_type))}-errors.yaml')

      raise Exception(
          f'{msg}'
          f'\nInput content\n{textwrap.indent(input_content_yaml, prefix="  ")}'
          f'\nError details\n{textwrap.indent(errors_yaml, prefix="  ")}'
          f'\n{msg}') from e

  model = await _Internal()
  warnings = _WarnModelExtras(path=[], thing=model)
  if strict == 'warn':
    for warning in warnings:
      print(warning.message, file=sys.stderr)
  elif strict == 'yes':
    for warning in warnings:
      raise Exception(warning.message)

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


class _WatchVar:

  def __init__(self, **kwargs):
    self._kwargs = kwargs

  def __enter__(self):
    pass

  def __exit__(self, exc_type, exc, tb):
    if exc is not None:
      print(
          f'{type(self).__name__}: Error occurred, and you are watching these variables:',
          file=sys.stderr)
      for key, value in self._kwargs.items():
        value_lines = str(value).split('\n')
        if len(value_lines) > 1:
          value = '\n' + textwrap.indent(value, prefix='    ')
        else:
          if isinstance(value, str):
            value = repr(value)
        print(f'  {key}: {value}', file=sys.stderr)
