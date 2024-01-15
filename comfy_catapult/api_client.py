# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT
#
# The Comfy Catapult project require contributions made to this file be licensed
# under the MIT license or a compatible open source license. See LICENSE.md for
# the license text.

import base64
import json
import textwrap
from typing import Any, Dict, Type, TypeVar
from urllib.parse import urlencode, urlparse

import aiohttp
from pydantic import BaseModel

from comfy_catapult.api_client_base import ComfyAPIClientBase
from comfy_catapult.comfy_schema import (APIHistory, APIObjectInfo,
                                         APIQueueInfo, APISystemStats,
                                         APIUploadImageResp, APIWorkflowTicket,
                                         ClientID, PromptID)
from comfy_catapult.comfy_utils import TryParseAsModel, YamlDump, _WatchVar
from comfy_catapult.url_utils import SmartURLJoin


async def _TryParseAsJson(*, content: str) -> Any:
  try:
    return json.loads(content)
  except json.JSONDecodeError as e:
    raise Exception(
        f'Error: {e}\n\nContent (raw): {textwrap.indent(content, prefix="  ")}'
    ) from e


async def _TryParseRespAsJson(*, resp: aiohttp.ClientResponse) -> Any:
  content_bytes = b''
  content_str: str = ''
  content: Any = {}
  try:
    content_bytes = await resp.content.read()
    content_str = content_bytes.decode('utf-8')
    if resp.content_type != 'application/json':
      raise Exception(
          f'Error: {resp.status} {resp.reason}'
          f'\n\nExpected content-type: application/json, got {resp.content_type}'
          f'\n\nContent (raw):\n{textwrap.indent(content_str, prefix="  ")}')

    content = await _TryParseAsJson(content=content_str)
    if resp.status != 200:
      raise Exception(
          f'Error: {resp.status} {resp.reason}'
          f'\n\nContent (yaml):\n{textwrap.indent(YamlDump(content), prefix="  ")}'
      )
    return content
  except Exception as e:
    contentb64 = base64.b64encode(content_bytes).decode('utf-8')
    raise Exception(
        f'Error: {resp.status} {resp.reason}'
        f'\n\nContent (raw):\n{textwrap.indent(content_str, prefix="  ")}'
        f'\n\nContent (yaml):\n{textwrap.indent(YamlDump(content), prefix="  ")}'
        f'\n\nContent (base64):\n{textwrap.indent(contentb64, prefix="  ")}'
    ) from e


_BaseModelT = TypeVar('_BaseModelT', bound=BaseModel)


async def _TryParseRespAsModel(*, resp: aiohttp.ClientResponse,
                               model_type: Type[_BaseModelT]) -> _BaseModelT:
  content: Any = await _TryParseRespAsJson(resp=resp)
  return await TryParseAsModel(content=content, model_type=model_type)


class ComfyAPIClient(ComfyAPIClientBase):

  def __init__(self, *, comfy_api_url: str):
    self._comfy_api_url = comfy_api_url
    self._session = aiohttp.ClientSession()

  async def __aenter__(self):
    return self

  async def __aexit__(self, exc_type, exc, tb):
    await self._session.__aexit__(exc_type, exc, tb)
    await self.Close()

  async def Close(self):
    await self._session.close()

  def GetURL(self) -> str:
    return self._comfy_api_url

  async def GetSystemStats(self) -> APISystemStats:
    url = urlparse(f'{self._comfy_api_url}/system_stats')
    with _WatchVar(url=url.geturl()):
      async with self._session.get(url.geturl()) as resp:
        return await _TryParseRespAsModel(resp=resp, model_type=APISystemStats)

  async def GetObjectInfoRaw(self) -> dict:
    url = urlparse(f'{self._comfy_api_url}/object_info')
    with _WatchVar(url=url.geturl()):
      async with self._session.get(url.geturl()) as resp:
        return await _TryParseRespAsJson(resp=resp)

  async def GetObjectInfo(self) -> APIObjectInfo:
    url = urlparse(f'{self._comfy_api_url}/object_info')
    with _WatchVar(url=url.geturl()):
      async with self._session.get(url.geturl()) as resp:
        return await _TryParseRespAsModel(resp=resp, model_type=APIObjectInfo)

  async def GetPromptRaw(self) -> dict:
    url = urlparse(f'{self._comfy_api_url}/prompt')
    with _WatchVar(url=url.geturl()):
      async with self._session.get(url.geturl()) as resp:
        return await _TryParseRespAsJson(resp=resp)

  async def PostPrompt(self,
                       *,
                       prompt_workflow: dict,
                       number: int | None = None,
                       client_id: ClientID | None = None,
                       prompt_id: PromptID | None = None,
                       extra_data: dict | None = None) -> APIWorkflowTicket:
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
    url = urlparse(f'{self._comfy_api_url}/prompt')
    with _WatchVar(url=url.geturl()):
      async with self._session.post(url.geturl(), data=data) as resp:
        return await _TryParseRespAsModel(resp=resp,
                                          model_type=APIWorkflowTicket)

  async def GetHistory(self,
                       *,
                       prompt_id: str | None = None,
                       max_items: int | None = None) -> APIHistory:
    url = urlparse(SmartURLJoin(f'{self._comfy_api_url}', '/history'))
    if max_items is not None:
      url = url._replace(query=f'max_items={max_items}')
    if prompt_id is not None:
      url = url._replace(path=f'{url.path}/{prompt_id}')

    with _WatchVar(url=url.geturl()):
      async with self._session.get(url.geturl()) as resp:
        return await _TryParseRespAsModel(resp=resp, model_type=APIHistory)

  async def GetQueue(self) -> APIQueueInfo:
    url = urlparse(SmartURLJoin(f'{self._comfy_api_url}', '/queue'))
    with _WatchVar(url=url.geturl()):
      async with self._session.get(url.geturl()) as resp:
        return await _TryParseRespAsModel(resp=resp, model_type=APIQueueInfo)

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
    with _WatchVar(folder_type=folder_type,
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
      post_url = urlparse(
          SmartURLJoin(f'{self._comfy_api_url}', '/upload/image'))
      with _WatchVar(post_url=post_url.geturl(), fdata=fdata):
        async with self._session.post(post_url.geturl(), data=fdata) as resp:
          result = await _TryParseRespAsJson(resp=resp)
          assert isinstance(result, dict), type(result)
          return result

  async def PostUploadImage(self, *, folder_type: str, subfolder: str,
                            filename: str, data: bytes,
                            overwrite: bool) -> APIUploadImageResp:
    result = await self.PostUploadImageRaw(folder_type=folder_type,
                                           subfolder=subfolder,
                                           filename=filename,
                                           data=data,
                                           overwrite=overwrite)
    return await TryParseAsModel(content=result, model_type=APIUploadImageResp)

  async def GetView(self, *, folder_type: str, subfolder: str,
                    filename: str) -> bytes:
    data = {'filename': filename, 'subfolder': subfolder, 'type': folder_type}
    url = urlparse(SmartURLJoin(f'{self._comfy_api_url}', '/view'))
    url = url._replace(query=urlencode(data))

    with _WatchVar(url=url.geturl()):
      async with self._session.get(url.geturl()) as resp:
        return await resp.content.read()
