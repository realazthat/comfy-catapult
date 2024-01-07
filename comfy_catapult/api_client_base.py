# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT
#
# The Catapult require contributions made to this file be licensed under the MIT
# license or a compatible open source license. See LICENSE.md for the license
# text.

from abc import ABC, abstractmethod

from comfy_catapult.comfy_schema import (APIHistory, APIObjectInfo,
                                         APIQueueInfo, APISystemStats,
                                         APIUploadImageResp, APIWorkflowTicket)


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
  async def PostPrompt(self, *, prompt_workflow: dict) -> APIWorkflowTicket:
    raise NotImplementedError()

  @abstractmethod
  async def GetHistory(self,
                       *,
                       prompt_id: str | None = None,
                       max_items: int | None = None) -> APIHistory:
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
