# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT
#
# The Comfy Catapult project requires contributions made to this file be licensed
# under the MIT license or a compatible open source license. See LICENSE.md for
# the license text.

from abc import ABC, abstractmethod
from typing import List

from comfy_catapult.comfy_schema import (APIHistory, APIObjectInfo,
                                         APIQueueInfo, APISystemStats,
                                         APIUploadImageResp, APIWorkflowTicket,
                                         ClientID, PromptID)


class ComfyAPIClientBase(ABC):

  @abstractmethod
  async def __aenter__(self):
    raise NotImplementedError()

  @abstractmethod
  async def __aexit__(self, exc_type, exc, tb):
    raise NotImplementedError()

  @abstractmethod
  def GetURL(self) -> str:
    raise NotImplementedError()

  @abstractmethod
  async def Close(self):
    raise NotImplementedError()

  @abstractmethod
  async def GetSystemStatsRaw(self) -> dict:
    raise NotImplementedError()

  @abstractmethod
  async def GetSystemStats(self) -> APISystemStats:
    raise NotImplementedError()

  @abstractmethod
  async def GetObjectInfoRaw(self) -> dict:
    """Returns all known nodes and their metadata.

    Gets the data from the `/object_info` endpoint.

    See test_data/object_info.yml for an example of the response.

    See APIObjectInfo documentation for more info.

    Returns:
        dict: The parsed json, as a python dict.
    """
    raise NotImplementedError()

  @abstractmethod
  async def GetObjectInfo(self) -> APIObjectInfo:
    """Returns all known nodes and their metadata.

    Gets the data from the `/object_info` endpoint.

    See APIObjectInfo documentation for more info.

    Returns:
        APIObjectInfo: The parsed response.
    """
    raise NotImplementedError()

  @abstractmethod
  async def GetPromptRaw(self) -> dict:
    raise NotImplementedError()

  @abstractmethod
  async def PostPromptRaw(self,
                          *,
                          prompt_workflow: dict,
                          number: int | None = None,
                          client_id: ClientID | None = None,
                          prompt_id: PromptID | None = None,
                          extra_data: dict | None = None) -> dict:
    """See `ComfyUI/server.py` `@routes.post("/prompt")`.

    Args:
        prompt_workflow (dict): The API workflow, you can generate this with
          the ComfyUI web interface, as explained in `README.md`:
          1. Open settings (gear box in the corner).
          2. Enable the ability to export in the API format, `Enable Dev mode Options`.
          3. Click new menu item `Save (API format)`.
        prompt_id (PromptID | None): If you want to set the prompt id. If you
          leave this empty, the server will generate a prompt id for you.
        number (int, optional): Where to insert into the queue. -1 means to
          insert to the front of the queue. Default is None, which uses the
          default on the server, which is also equivalent to -1.
        client_id (ClientID | None, optional): _description_. Defaults to None.
        extra_data (dict | None, optional): Extra data associated with the
          prompt/job. Defaults to None.

    Returns:
        dict: The json response.
    """
    raise NotImplementedError()

  @abstractmethod
  async def PostPrompt(self,
                       *,
                       prompt_workflow: dict,
                       number: int | None = None,
                       client_id: ClientID | None = None,
                       prompt_id: PromptID | None = None,
                       extra_data: dict | None = None) -> APIWorkflowTicket:
    """See `ComfyUI/server.py` `@routes.post("/prompt")`.

    Args:
        prompt_workflow (dict): The API workflow, you can generate this with
          the ComfyUI web interface, as explained in `README.md`:
          1. Open settings (gear box in the corner).
          2. Enable the ability to export in the API format, `Enable Dev mode Options`.
          3. Click new menu item `Save (API format)`.
        prompt_id (PromptID | None): If you want to set the prompt id. If you
          leave this empty, the server will generate a prompt id for you.
        number (int, optional): Where to insert into the queue. -1 means to
          insert to the front of the queue. Default is None, which uses the
          default on the server, which is also equivalent to -1.
        client_id (ClientID | None, optional): _description_. Defaults to None.
        extra_data (dict | None, optional): Extra data associated with the
          prompt/job. Defaults to None.

    Returns:
        APIWorkflowTicket: The response parsed into a pydantic model.
    """
    raise NotImplementedError()

  @abstractmethod
  async def GetHistoryRaw(self,
                          *,
                          prompt_id: PromptID | None = None,
                          max_items: int | None = None) -> dict:
    raise NotImplementedError()

  @abstractmethod
  async def GetHistory(self,
                       *,
                       prompt_id: PromptID | None = None,
                       max_items: int | None = None) -> APIHistory:
    raise NotImplementedError()

  @abstractmethod
  async def GetQueueRaw(self) -> dict:
    raise NotImplementedError()

  @abstractmethod
  async def GetQueue(self) -> APIQueueInfo:
    raise NotImplementedError()

  @abstractmethod
  async def GetView(self, *, folder_type: str, subfolder: str,
                    filename: str) -> bytes:
    raise NotImplementedError()

  @abstractmethod
  async def PostUploadImageRaw(self, *, folder_type: str, subfolder: str,
                               filename: str, data: bytes,
                               overwrite: bool) -> dict:
    raise NotImplementedError()

  @abstractmethod
  async def PostUploadImage(self, *, folder_type: str, subfolder: str,
                            filename: str, data: bytes,
                            overwrite: bool) -> APIUploadImageResp:
    raise NotImplementedError()

  @abstractmethod
  async def PostFree(self, *, unload_models: bool, free_memory: bool):
    raise NotImplementedError()

  @abstractmethod
  async def PostInterrupt(self):
    raise NotImplementedError()

  @abstractmethod
  async def PostQueue(self, *, delete: List[PromptID], clear: bool):
    raise NotImplementedError()
