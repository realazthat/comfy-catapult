# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT
#
# The Comfy Catapult project requires contributions made to this file be licensed
# under the MIT license or a compatible open source license. See LICENSE.md for
# the license text.

import base64
import json
import logging
import textwrap
from typing import Any, Dict, List, Optional, Type, TypeVar, Union
from urllib.parse import urlencode, urlparse

import aiohttp
from anyio import Path
from pydantic import BaseModel

from ._internal.url_utils import JoinToBaseURL
from ._internal.utilities import DumpYaml, TryParseAsModel, WatchVar
from .api_client_base import ComfyAPIClientBase
from .comfy_schema import (APIHistory, APIObjectInfo, APIPromptInfo,
                           APIQueueInfo, APISystemStats, APIUploadImageResp,
                           APIWorkflowTicket, ClientID, PromptID)

logger = logging.getLogger(__name__)

T = TypeVar('T')


async def _TryGetContent(*,
                         resp: aiohttp.ClientResponse) -> Union[str, Exception]:
  try:
    return await resp.text(errors='replace')
  except Exception as e:
    logger.exception('Error getting content', exc_info=e, stack_info=True)
    return e


async def _RaiseForStatus(*,
                          resp: aiohttp.ClientResponse,
                          extra: Optional[Any] = None):
  """Same as raise_for_status(), but also dumps any content in the response into the exception"""
  try:
    resp.raise_for_status()
  except aiohttp.ClientResponseError as e:
    content_or_exc = await _TryGetContent(resp=resp)

    message = e.message
    if isinstance(content_or_exc, str):
      message += f'\n\nContent (raw): {textwrap.indent(content_or_exc, prefix="  ")}'
    else:
      message += f'\n\nError getting content: {content_or_exc}'
    if extra is not None:
      message += f'\n\nExtra info: {textwrap.indent(await DumpYaml(extra), prefix="  ")}'

    raise aiohttp.ClientResponseError(request_info=e.request_info,
                                      history=e.history,
                                      code=e.code,
                                      status=e.status,
                                      message=message,
                                      headers=e.headers) from e


async def _TryParseAsJson(*, content: str, json_type: Type[T]) -> T:
  try:
    result = json.loads(content)
    if not isinstance(result, json_type):
      raise TypeError(f'Expected {json_type}, got {type(result)}')
    return result
  except json.JSONDecodeError as e:
    raise Exception(
        f'Error: {e}\n\nContent (raw): {textwrap.indent(content, prefix="  ")}'
    ) from e


async def _TryParseRespAsJson(*, resp: aiohttp.ClientResponse,
                              json_type: Type[T]) -> T:
  content_bytes = b''
  content_str: str = ''
  content: Optional[T] = None
  try:
    content_bytes = await resp.content.read()
    content_str = content_bytes.decode('utf-8')
    if resp.content_type != 'application/json':
      raise Exception(
          f'Error: {resp.status} {resp.reason}'
          f'\n\nExpected content-type: application/json, got {resp.content_type}'
          f'\n\nContent (raw):\n{textwrap.indent(content_str, prefix="  ")}')

    content = await _TryParseAsJson(content=content_str, json_type=json_type)
    if resp.ok:
      await _RaiseForStatus(resp=resp, extra=content)
    return content
  except Exception as e:
    contentb64 = base64.b64encode(content_bytes).decode('utf-8')
    raise Exception(
        f'Error: {resp.status} {resp.reason}'
        f'\n\nContent (raw):\n{textwrap.indent(content_str, prefix="  ")}'
        f'\n\nContent (yaml):\n{textwrap.indent(await DumpYaml(content), prefix="  ")}'
        f'\n\nContent (base64):\n{textwrap.indent(contentb64, prefix="  ")}'
    ) from e


_BaseModelT = TypeVar('_BaseModelT', bound=BaseModel)


async def _TryParseRespAsModel(
    *, resp: aiohttp.ClientResponse, model_type: Type[_BaseModelT],
    errors_dump_directory: Optional[Path]) -> _BaseModelT:
  content: Any = await _TryParseRespAsJson(resp=resp, json_type=dict)
  return await TryParseAsModel(content=content,
                               model_type=model_type,
                               errors_dump_directory=errors_dump_directory)


class ComfyAPIClient(ComfyAPIClientBase):

  def __init__(self,
               comfy_api_url: str,
               *,
               errors_dump_directory: Optional[Path] = None):
    self._comfy_api_url = comfy_api_url
    self._session = aiohttp.ClientSession()
    self._errors_dump_directory = errors_dump_directory

  async def __aenter__(self):
    await self._session.__aenter__()
    return self

  async def __aexit__(self, exc_type, exc, tb):
    await self._session.__aexit__(exc_type, exc, tb)
    await self.Close()

  async def Close(self):
    await self._session.close()

  def GetURL(self) -> str:
    return self._comfy_api_url

  async def GetSystemStatsRaw(self) -> dict:
    url = urlparse(JoinToBaseURL(self._comfy_api_url, 'system_stats'))
    async with WatchVar(url=url.geturl()):
      async with self._session.get(url.geturl()) as resp:
        return await _TryParseRespAsJson(resp=resp, json_type=dict)

  async def GetSystemStats(self) -> APISystemStats:
    url = urlparse(JoinToBaseURL(self._comfy_api_url, 'system_stats'))
    async with WatchVar(url=url.geturl()):
      async with self._session.get(url.geturl()) as resp:
        return await _TryParseRespAsModel(
            resp=resp,
            model_type=APISystemStats,
            errors_dump_directory=self._errors_dump_directory)

  async def GetObjectInfoRaw(self) -> dict:
    url = urlparse(JoinToBaseURL(self._comfy_api_url, 'object_info'))
    async with WatchVar(url=url.geturl()):
      async with self._session.get(url.geturl()) as resp:
        return await _TryParseRespAsJson(resp=resp, json_type=dict)

  async def GetObjectInfo(self) -> APIObjectInfo:
    url = urlparse(JoinToBaseURL(self._comfy_api_url, 'object_info'))
    async with WatchVar(url=url.geturl()):
      async with self._session.get(url.geturl()) as resp:
        return await _TryParseRespAsModel(
            resp=resp,
            model_type=APIObjectInfo,
            errors_dump_directory=self._errors_dump_directory)

  async def GetPromptRaw(self) -> dict:
    url = urlparse(JoinToBaseURL(self._comfy_api_url, 'prompt'))
    async with WatchVar(url=url.geturl()):
      async with self._session.get(url.geturl()) as resp:
        return await _TryParseRespAsJson(resp=resp, json_type=dict)

  async def GetPrompt(self) -> APIPromptInfo:
    prompt_info_dict = await self.GetPromptRaw()
    return await TryParseAsModel(
        content=prompt_info_dict,
        model_type=APIPromptInfo,
        errors_dump_directory=self._errors_dump_directory)

  async def PostPromptRaw(self,
                          *,
                          prompt_workflow: dict,
                          number: Optional[int] = None,
                          client_id: Optional[ClientID] = None,
                          prompt_id: Optional[PromptID] = None,
                          extra_data: Optional[dict] = None) -> dict:
    body: Dict[str, Any] = {'prompt': prompt_workflow}

    if number is not None:
      body['number'] = number
    if client_id is not None:
      body['client_id'] = client_id
    if prompt_id is not None:
      body['prompt_id'] = prompt_id
    if extra_data is not None:
      body['extra_data'] = extra_data

    data: bytes = json.dumps(body).encode('utf-8')
    url = urlparse(JoinToBaseURL(self._comfy_api_url, 'prompt'))
    async with WatchVar(url=url.geturl()):
      async with self._session.post(url.geturl(), data=data) as resp:
        return await _TryParseRespAsJson(resp=resp, json_type=dict)

  async def PostPrompt(self,
                       *,
                       prompt_workflow: dict,
                       number: Optional[int] = None,
                       client_id: Optional[ClientID] = None,
                       prompt_id: Optional[PromptID] = None,
                       extra_data: Optional[dict] = None) -> APIWorkflowTicket:
    ticket = await self.PostPromptRaw(prompt_workflow=prompt_workflow,
                                      number=number,
                                      client_id=client_id,
                                      prompt_id=prompt_id,
                                      extra_data=extra_data)
    return await TryParseAsModel(
        content=ticket,
        model_type=APIWorkflowTicket,
        errors_dump_directory=self._errors_dump_directory)

  async def GetHistoryRaw(self,
                          *,
                          prompt_id: Optional[PromptID] = None,
                          max_items: Optional[int] = None) -> dict:
    url = urlparse(JoinToBaseURL(self._comfy_api_url, 'history'))
    if max_items is not None:
      url = url._replace(query=f'max_items={max_items}')
    if prompt_id is not None:
      url = url._replace(path=f'{url.path}/{prompt_id}')

    async with WatchVar(url=url.geturl()):
      async with self._session.get(url.geturl()) as resp:
        return await _TryParseRespAsJson(resp=resp, json_type=dict)

  async def GetHistory(self,
                       *,
                       prompt_id: Optional[PromptID] = None,
                       max_items: Optional[int] = None) -> APIHistory:
    history = await self.GetHistoryRaw(prompt_id=prompt_id, max_items=max_items)
    return await TryParseAsModel(
        content=history,
        model_type=APIHistory,
        errors_dump_directory=self._errors_dump_directory)

  async def GetQueueRaw(self) -> dict:
    url = urlparse(JoinToBaseURL(self._comfy_api_url, 'queue'))
    async with WatchVar(url=url.geturl()):
      async with self._session.get(url.geturl()) as resp:
        return await _TryParseRespAsJson(resp=resp, json_type=dict)

  async def GetQueue(self) -> APIQueueInfo:
    queue: dict = await self.GetQueueRaw()
    return await TryParseAsModel(
        content=queue,
        model_type=APIQueueInfo,
        errors_dump_directory=self._errors_dump_directory)

  async def PostUploadImageRaw(self, *, folder_type: str, subfolder: str,
                               filename: str, data: bytes,
                               overwrite: bool) -> dict:
    """

    * See https://github.com/comfyanonymous/ComfyUI/blob/0c2c9fbdfa53c2ad3b7658a7f2300da831830388/server.py#L203

    * See https://github.com/comfyanonymous/ComfyUI/blob/0c2c9fbdfa53c2ad3b7658a7f2300da831830388/server.py#L161

    Args:
        folder_type (str): _description_
        subfolder (str): _description_
        filename (str): _description_
        data (bytes): _description_
        overwrite (bool): _description_

    Returns:
        dict: _description_
    """
    async with WatchVar(folder_type=folder_type,
                        subfolder=subfolder,
                        filename=filename,
                        overwrite=overwrite):
      fdata = aiohttp.FormData()
      fdata.add_field('image',
                      data,
                      filename=filename,
                      content_type='application/octet-stream')
      fdata.add_field('overwrite', str(overwrite).lower())
      fdata.add_field('subfolder', subfolder)
      fdata.add_field('type', folder_type)
      fdata.add_field('filename', filename)
      post_url = urlparse(JoinToBaseURL(self._comfy_api_url, 'upload/image'))
      async with WatchVar(post_url=post_url.geturl(), fdata=fdata):
        async with self._session.post(post_url.geturl(), data=fdata) as resp:
          result = await _TryParseRespAsJson(resp=resp, json_type=dict)
          if not isinstance(result, dict):
            # Server should never return a list or something other than a
            # dictionary.
            raise TypeError(f'Expected dict, got {type(result)}')
          return result

  async def PostUploadImage(self, *, folder_type: str, subfolder: str,
                            filename: str, data: bytes,
                            overwrite: bool) -> APIUploadImageResp:
    result = await self.PostUploadImageRaw(folder_type=folder_type,
                                           subfolder=subfolder,
                                           filename=filename,
                                           data=data,
                                           overwrite=overwrite)
    return await TryParseAsModel(
        content=result,
        model_type=APIUploadImageResp,
        errors_dump_directory=self._errors_dump_directory)

  async def GetView(self, *, folder_type: str, subfolder: str,
                    filename: str) -> bytes:
    data = {'filename': filename, 'subfolder': subfolder, 'type': folder_type}
    url = urlparse(JoinToBaseURL(self._comfy_api_url, 'view'))
    url = url._replace(query=urlencode(data))

    async with WatchVar(url=url.geturl()):
      async with self._session.get(url.geturl()) as resp:
        await _RaiseForStatus(resp=resp)
        return await resp.content.read()

  async def PostFree(self, *, unload_models: bool, free_memory: bool):
    data = {'unload_models': unload_models, 'free_memory': free_memory}
    url = urlparse(JoinToBaseURL(self._comfy_api_url, 'free'))
    async with WatchVar(url=url.geturl()):
      async with self._session.post(url.geturl(), data=data) as resp:
        await _RaiseForStatus(resp=resp)

  async def PostInterrupt(self):
    # TODO(realazthat/comfy-catapult#5): change the API to take a prompt_id.
    url = urlparse(JoinToBaseURL(self._comfy_api_url, 'interrupt'))
    async with WatchVar(url=url.geturl()):
      async with self._session.post(url.geturl()) as resp:
        resp.raise_for_status()

  async def PostQueue(self, *, delete: List[PromptID], clear: bool):
    url = urlparse(JoinToBaseURL(self._comfy_api_url, 'queue'))
    data = {'delete': delete, 'clear': clear}
    async with WatchVar(url=url.geturl()):
      async with self._session.post(url.geturl(), data=data) as resp:
        resp.raise_for_status()
