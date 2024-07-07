# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT
#
# The Comfy Catapult project requires contributions made to this file be licensed
# under the MIT license or a compatible open source license. See LICENSE.md for
# the license text.

import asyncio
import base64
import dataclasses
import datetime
import functools
import json
import logging
import sys
import textwrap
import traceback
from dataclasses import is_dataclass
from typing import (Any, Callable, Dict, Generator, List, Literal, NamedTuple,
                    Optional, Type, TypeVar)
from urllib.parse import unquote as paramdecode
from urllib.parse import urlparse

import aiofiles
import pydantic_core
import yaml
from anyio import Path
from pydantic import BaseModel
from pydash import slugify

from .url_utils import JoinToBaseURL

MAX_DUMP_LINES: Optional[int] = 200
_BaseModelT = TypeVar('_BaseModelT', bound=BaseModel)
logger = logging.getLogger(__name__)

if sys.version_info >= (3, 9):
  from asyncio import to_thread
else:
  T = TypeVar('T')

  async def to_thread(func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
    """Run a function in a separate thread."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None,
                                      functools.partial(func, *args, **kwargs))


class _CustomDumper(yaml.Dumper):

  def represent_tuple(self, data):
    return self.represent_list(data)


_CustomDumper.add_representer(tuple, _CustomDumper.represent_tuple)


async def DumpModelToDict(model: BaseModel, **kwargs) -> Dict[str, Any]:
  if 'by_alias' not in kwargs:
    kwargs['by_alias'] = True
  if 'round_trip' not in kwargs:
    kwargs['round_trip'] = True
  if 'mode' not in kwargs:
    kwargs['mode'] = 'json'
  return await to_thread(model.model_dump, **kwargs)


async def DumpYaml(data: Any) -> str:
  return await to_thread(yaml.dump,
                         data,
                         indent=2,
                         Dumper=_CustomDumper,
                         sort_keys=False)


async def DumpModelToYAML(model: BaseModel, **kwargs) -> str:
  model_dict = await DumpModelToDict(model)
  return await DumpYaml(model_dict)


async def DumpBigYaml(data: Any, *, max_lines: Optional[int],
                      path: Path) -> str:
  yaml_str = await DumpYaml(data)
  line_count = len(yaml_str.splitlines())
  if max_lines is None or line_count <= max_lines:
    return yaml_str

  await path.parent.mkdir(parents=True, exist_ok=True)
  async with aiofiles.open(path, 'w') as f:
    await f.write(yaml_str)
  return f'Too large, see {json.dumps(str(path))}'


async def DumpBigErrorStr(exception: Exception, max_lines: Optional[int],
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


def BasicAuthToHeaders(*, url: str, headers: Dict[str, str]) -> str:
  """
  websockets lib doessn't support basic auth in the url, so we have to move it
  to the headers.
  """
  url_pr = urlparse(url)
  if url_pr.username is None and url_pr.password is None:
    return url

  username = url_pr.username or ''
  password = url_pr.password or ''

  # urldecode the username and password
  username = paramdecode(username)
  password = paramdecode(password)
  auth = f'{username}:{password}'
  encoded_auth = base64.b64encode(auth.encode()).decode()

  headers['Authorization'] = f'Basic {encoded_auth}'
  new_netloc = f'{url_pr.hostname}:{url_pr.port}'
  return url_pr._replace(netloc=new_netloc).geturl()


def GetWebSocketURL(*, comfy_api_url: str, client_id: str) -> str:
  ws_url_str = JoinToBaseURL(comfy_api_url, 'ws')
  ws_url = urlparse(ws_url_str)
  if ws_url.scheme == 'https':
    ws_url = ws_url._replace(scheme='wss')
  else:
    ws_url = ws_url._replace(scheme='ws')
  ws_url = ws_url._replace(query=f'clientId={client_id}')
  return ws_url.geturl()


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
        return await to_thread(model_type.model_validate,
                               content,
                               strict=strict in ['yes', 'warn'])
      except pydantic_core.ValidationError as e:
        if strict == 'yes':
          # Go to the except below which just prints the error.
          raise
        # Try parsing it non-strictly, and then warn about the error if it
        # succeeds. If it errors, then we'll go to the except below which
        # prints the error.
        model = await to_thread(model_type.model_validate,
                                content,
                                strict=False)
        if error_dump_path is None and errors_dump_directory is not None:
          error_dump_path = await _GetNewPath(parent_path=errors_dump_directory)

        if error_dump_path is not None:
          error_line = await DumpBigErrorStr(
              exception=e,
              max_lines=MAX_DUMP_LINES,
              path=error_dump_path /
              f'{slugify(str(model_type))}-error_str.txt')

          model_dump_yaml = await DumpBigYaml(
              to_thread(model.model_dump,
                        mode='json',
                        by_alias=True,
                        round_trip=True),
              max_lines=MAX_DUMP_LINES,
              path=error_dump_path /
              f'{slugify(str(model_type))}-model_dump.yaml')
          input_content_yaml = await DumpBigYaml(
              content,
              max_lines=MAX_DUMP_LINES,
              path=error_dump_path /
              f'{slugify(str(model_type))}-input_content.yaml')
        else:
          error_line = str(e)
          model_dump_yaml = await DumpModelToYAML(model)
          input_content_yaml = await DumpYaml(content)

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
        error_line = await DumpBigErrorStr(
            exception=e,
            max_lines=MAX_DUMP_LINES,
            path=error_dump_path / f'{slugify(str(model_type))}-error_str.txt')
      else:
        error_line = str(e)
      msg_summary = f'Error parsing {model_type}: {error_line}'
      msg = f'{msg_summary}'
      if error_dump_path is not None:
        input_content_yaml = await DumpBigYaml(
            content,
            max_lines=MAX_DUMP_LINES,
            path=error_dump_path /
            f'{slugify(str(model_type))}-input_content.yaml')
        msg += '\nInput content\n' + textwrap.indent(input_content_yaml,
                                                     prefix='  ')
        errors_yaml = await DumpBigYaml(
            e.errors(),
            max_lines=MAX_DUMP_LINES,
            path=error_dump_path / f'{slugify(str(model_type))}-errors.yaml')
        msg += '\nError details\n' + textwrap.indent(errors_yaml, prefix='  ')
      else:
        msg += '\nInput content\n' + textwrap.indent(await DumpYaml(content),
                                                     prefix='  ')
        msg += '\nError details\n' + textwrap.indent(await DumpYaml(e.errors()),
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
  return model


class WatchVar:

  def __init__(self, **kwargs):
    self._kwargs = kwargs

  async def __aenter__(self):
    pass

  async def __aexit__(self, exc_type, exc, tb):
    if exc is not None:
      if isinstance(exc, (KeyboardInterrupt, SystemExit, asyncio.CancelledError,
                          BaseException)):
        return

      extra: Dict[str, Any] = {}
      if exc_type is not None:
        extra['exc_type'] = type(exc_type).__name__
      extra['kwargs'] = self._kwargs
      extra['tb'] = traceback.format_tb(tb)

      logger.error(
          f'{type(self).__name__}: Error occurred: {json.dumps(str(exc))} ({type(exc).__name__})'
          f'\nTraceback:\n{textwrap.indent("".join(traceback.format_tb(tb)), "  ")}'
          f'\nYou are watching these variables:\n{textwrap.indent(await DumpYaml(self._kwargs), "  ")}',
          extra=extra)
