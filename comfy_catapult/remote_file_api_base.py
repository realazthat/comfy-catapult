# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT
#
# The Comfy Catapult project requires contributions made to this file be licensed
# under the MIT license or a compatible open source license. See LICENSE.md for
# the license text.

from abc import ABC, abstractmethod
from urllib.parse import ParseResult

from anyio import Path

from comfy_catapult.url_utils import ComfyUIPathTriplet

EMPTY_URL = ParseResult(scheme='',
                        netloc='',
                        path='',
                        params='',
                        query='',
                        fragment='')


class RemoteFileAPIBase(ABC):

  @abstractmethod
  async def UploadFile(self, *, src_path: Path, untrusted_dst_url: str) -> str:
    """Upload a file.

    Args:
        src_path (Path): _description_
        untrusted_dst_url (str): _description_


    Returns:
        str: A new URL, sometimes the stored URL is not the same as the uploaded
        one, e.g if there is already an existing file there.
    """
    raise NotImplementedError()

  async def UploadToTriplet(
      self, *, src_path: Path,
      untrusted_dst_triplet: ComfyUIPathTriplet) -> ComfyUIPathTriplet:
    """Upload a file to a (comfy api server, folder_type, subfolder, filename).

    Raises:
        NotImplementedError: _description_

    Returns:
        ComfyUIPathTriplet: A new triplet, sometimes the stored triplet is not
        the same as the uploaded one, e.g if there is already an existing file
        there.
    """
    raise NotImplementedError()

  @abstractmethod
  async def DownloadFile(self, *, untrusted_src_url: str, dst_path: Path):
    raise NotImplementedError()

  @abstractmethod
  async def DownloadTriplet(self, *, untrusted_src_triplet: ComfyUIPathTriplet,
                            dst_path: Path):
    raise NotImplementedError()

  @abstractmethod
  def TripletToURL(self, *, triplet: ComfyUIPathTriplet) -> str:
    """Convert a triplet, that this API can handle, to a URL that this API can handle."""
    raise NotImplementedError()

  @abstractmethod
  def URLToTriplet(self, *, url: str) -> ComfyUIPathTriplet:
    """Convert a URL that this API can handle to a triplet, that this API can handle."""
    raise NotImplementedError()

  @abstractmethod
  def GetBases(self) -> list[str]:
    """Return a list of base URLs that this API can handle."""
    raise NotImplementedError()
