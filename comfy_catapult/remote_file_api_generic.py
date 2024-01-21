# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT
#
# The Comfy Catapult project require contributions made to this file be licensed
# under the MIT license or a compatible open source license. See LICENSE.md for
# the license text.

from collections import defaultdict
from typing import Dict, List

from anyio import Path

from comfy_catapult.remote_file_api_base import RemoteFileAPIBase
from comfy_catapult.url_utils import ComfyUIPathTriplet, IsWeaklyRelativeTo


class GenericRemoteFileAPI(RemoteFileAPIBase):
  """Download or upload files from a URL, using multiple schemss.
  """

  def __init__(self):
    super().__init__()
    self._base_to_api: Dict[str, List[RemoteFileAPIBase]] = defaultdict(list)

  def Register(self, api: RemoteFileAPIBase):
    for base in api.GetBases():
      self._base_to_api[base].append(api)

  def _GetAPIsForURL(self, *, url: str) -> List[RemoteFileAPIBase]:
    apis = []
    for base, api in self._base_to_api.items():
      if IsWeaklyRelativeTo(base=base, url=url):
        apis.append(api)
    if apis:
      return apis
    raise ValueError(f'URL {url} is not relative to any of'
                     f' {self._base_to_api.keys()}, there is no API registered'
                     f' to handle such URLs')

  def _GetAPIsForTriplet(
      self, *, triplet: ComfyUIPathTriplet) -> List[RemoteFileAPIBase]:
    relevant_apis = []
    convered_urls = []
    for base, base_apis in self._base_to_api.items():
      for api in base_apis:
        try:
          url = api.TripletToURL(triplet=triplet)
        except NotImplementedError:
          continue

        convered_urls.append({'base': base, 'url': url})
        if IsWeaklyRelativeTo(base=base, url=url):
          relevant_apis.append(api)
    if relevant_apis:
      return relevant_apis
    raise ValueError(f'ComfyUI API server URL {repr(triplet.comfy_api_url)}:'
                     ' there is no API registered to handle this URL'
                     f'\n triplet: {triplet}'
                     f'\n convered_urls: {convered_urls}')

  async def UploadFile(self, *, src_path: Path, untrusted_dst_url: str) -> str:
    if not await src_path.exists():
      raise ValueError(f'File {src_path} does not exist')
    if not await src_path.is_file():
      raise ValueError(f'File {src_path} is not a file')

    apis: List[RemoteFileAPIBase] = self._GetAPIsForURL(url=untrusted_dst_url)
    for i, api in enumerate(apis):
      try:
        return await api.UploadFile(src_path=src_path,
                                    untrusted_dst_url=untrusted_dst_url)
      except ValueError:
        if i + 1 >= len(apis):
          raise
    raise AssertionError('unreachable')

  async def UploadToTriplet(
      self, *, src_path: Path,
      untrusted_dst_triplet: ComfyUIPathTriplet) -> ComfyUIPathTriplet:
    if not await src_path.exists():
      raise ValueError(f'File {src_path} does not exist')
    if not await src_path.is_file():
      raise ValueError(f'File {src_path} is not a file')

    apis: List[RemoteFileAPIBase] = self._GetAPIsForTriplet(
        triplet=untrusted_dst_triplet)

    for i, api in enumerate(apis):
      try:
        return await api.UploadToTriplet(
            src_path=src_path, untrusted_dst_triplet=untrusted_dst_triplet)
      except ValueError:
        if i + 1 >= len(apis):
          raise
    raise AssertionError('unreachable')

  async def DownloadFile(self, *, untrusted_src_url: str, dst_path: Path):
    apis: List[RemoteFileAPIBase] = self._GetAPIsForURL(url=untrusted_src_url)
    for i, api in enumerate(apis):
      try:
        return await api.DownloadFile(untrusted_src_url=untrusted_src_url,
                                      dst_path=dst_path)
      except ValueError:
        if i + 1 >= len(apis):
          raise
    raise AssertionError('unreachable')

  async def DownloadTriplet(self, *, untrusted_src_triplet: ComfyUIPathTriplet,
                            dst_path: Path):
    apis: List[RemoteFileAPIBase] = self._GetAPIsForTriplet(
        triplet=untrusted_src_triplet)
    for i, api in enumerate(apis):
      try:
        return await api.DownloadTriplet(
            untrusted_src_triplet=untrusted_src_triplet, dst_path=dst_path)
      except ValueError:
        if i + 1 >= len(apis):
          raise
    raise AssertionError('unreachable')

  def TripletToURL(self, *, triplet: ComfyUIPathTriplet) -> str:
    apis: List[RemoteFileAPIBase] = self._GetAPIsForTriplet(triplet=triplet)
    for i, api in enumerate(apis):
      try:
        return api.TripletToURL(triplet=triplet)
      except ValueError:
        if i + 1 >= len(apis):
          raise
    raise AssertionError('unreachable')

  def URLToTriplet(self, *, url: str) -> ComfyUIPathTriplet:
    apis: List[RemoteFileAPIBase] = self._GetAPIsForURL(url=url)
    for i, api in enumerate(apis):
      try:
        return api.URLToTriplet(url=url)
      except (NotImplementedError, ValueError):
        if i + 1 >= len(apis):
          raise
    raise AssertionError('unreachable')

  def GetBases(self) -> list[str]:
    return list(self._base_to_api.keys())
