# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT
#
# The Catapult require contributions made to this file be licensed under the MIT
# license or a compatible open source license. See LICENSE.md for the license
# text.

from typing import List

import aioshutil
from anyio import Path

from comfy_catapult.remote_file_api_base import RemoteFileAPIBase
from comfy_catapult.url_utils import (ComfyUIPathTriplet, ToParseResult,
                                      ValidateIsBasedURL)


async def _LocalFileURLToLocalPath(url: str) -> Path:
  url_pr = ToParseResult(url)
  if url_pr.scheme != 'file':
    raise ValueError(f'URL {repr(url)} is not a file:// URL')
  assert url_pr.netloc == ''
  assert url_pr.params == ''
  assert url_pr.query == ''
  assert url_pr.fragment == ''
  assert url_pr.path.startswith('/')
  path = Path(url_pr.path)
  path = await path.resolve()
  assert path.is_absolute()
  return path


async def _IsLocalPathWeaklyRelative(*, base: Path, path: Path) -> bool:
  base = await base.resolve()
  path = await path.resolve()
  return path.is_relative_to(base)


async def _ValidateLocalPath(*, path: Path, any_bases: List[Path]) -> Path:
  for base in any_bases:
    if await _IsLocalPathWeaklyRelative(base=base, path=path):
      return path
  raise ValueError(f'Path {path} is not relative to any of {any_bases}')


class LocalRemoteFileAPI(RemoteFileAPIBase):
  """This one uses file:/// protocol on the local system.

  It is probably faster. In the future, I hope to add other protocols, so this
  can be used with other a choice remote storage systems as transparently as
  possible.
  """

  def __init__(self, *, upload_to_bases: List[str],
               download_from_bases: List[str]):
    super().__init__()
    self._upload_to_bases = upload_to_bases
    self._download_from_bases = download_from_bases

  async def UploadFile(self, *, src_path: Path, untrusted_dst_url: str) -> str:
    trusted_dst_url = ValidateIsBasedURL(url=untrusted_dst_url,
                                         any_bases=self._upload_to_bases)
    scheme = ToParseResult(trusted_dst_url).scheme
    assert scheme == 'file'
    assert await src_path.exists()
    assert await src_path.is_file()
    untrusted_dst_path = await _LocalFileURLToLocalPath(url=trusted_dst_url)
    trusted_dst_path = await _ValidateLocalPath(
        path=untrusted_dst_path,
        any_bases=[
            await _LocalFileURLToLocalPath(url=base)
            for base in self._upload_to_bases
        ])

    await trusted_dst_path.parent.mkdir(parents=True, exist_ok=True)
    await aioshutil.copy(src_path, trusted_dst_path)
    return trusted_dst_url

  async def DownloadFile(self, *, untrusted_src_url: str, dst_path: Path):
    trusted_src_url = ValidateIsBasedURL(url=untrusted_src_url,
                                         any_bases=self._download_from_bases)
    scheme = ToParseResult(trusted_src_url).scheme
    assert scheme == 'file'

    untrusted_src_path = await _LocalFileURLToLocalPath(url=trusted_src_url)
    trusted_src_path = await _ValidateLocalPath(
        path=untrusted_src_path,
        any_bases=[
            await _LocalFileURLToLocalPath(url=base)
            for base in self._download_from_bases
        ])

    assert await trusted_src_path.exists()
    assert await trusted_src_path.is_file()

    await dst_path.parent.mkdir(parents=True, exist_ok=True)
    await aioshutil.copy(trusted_src_path, dst_path)

  async def DownloadTriplet(self, *, untrusted_src_triplet: ComfyUIPathTriplet,
                            dst_path: Path):
    # TODO: Maybe we can make a mapper that maps triplets to urls, and then
    # download the file from the URL. But this is not necessary right now,
    # because you can use the ComfyAPIRemoteFileAPI to download triplets,
    # and the GenericRemoteFileAPI to handle it transparently by choosing
    # the RemoteAPIFileBase.
    raise NotImplementedError('Local files do not support triplets')

  async def UploadToTriplet(
      self, *, src_triplet: ComfyUIPathTriplet,
      untrusted_dst_triplet: ComfyUIPathTriplet) -> ComfyUIPathTriplet:
    # TODO: Maybe we can make a mapper that maps triplets to urls, and then
    # download the file from the URL. But this is not necessary right now,
    # because you can use the ComfyAPIRemoteFileAPI to download triplets,
    # and the GenericRemoteFileAPI to handle it transparently by choosing
    # the RemoteAPIFileBase.
    raise NotImplementedError('Local files do not support triplets')

  def TripletToURL(self, *, triplet: ComfyUIPathTriplet) -> str:
    raise NotImplementedError('Local files do not support triplets')

  def URLToTriplet(self, *, url: str) -> ComfyUIPathTriplet:
    raise NotImplementedError('Local files do not support triplets')

  def GetBases(self) -> list[str]:
    return list(self._upload_to_bases + self._download_from_bases)
