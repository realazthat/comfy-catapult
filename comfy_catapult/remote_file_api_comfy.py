# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT
#
# The Comfy Catapult project require contributions made to this file be licensed
# under the MIT license or a compatible open source license. See LICENSE.md for
# the license text.

from typing import List
from urllib.parse import ParseResult

from anyio import Path

from comfy_catapult.api_client import ComfyAPIClient
from comfy_catapult.comfy_schema import APIUploadImageResp
from comfy_catapult.remote_file_api_base import RemoteFileAPIBase
from comfy_catapult.url_utils import (VALID_COMFY_API_SCHEMES,
                                      VALID_FOLDER_TYPES, ComfyUIPathTriplet,
                                      SmartURLJoin, ToParseResult,
                                      ValidateIsBasedURL,
                                      ValidateIsComfyAPITargetURL)

VALID_COMFY_SCHEME_SCHEMES = ['comfy+http', 'comfy+https']


def _ValidateComfyAPITargetURL(url: str, *,
                               any_api_targets: List[str] | None) -> str:
  url_pr = ToParseResult(url=url)
  if url_pr.scheme not in VALID_COMFY_API_SCHEMES:
    raise ValueError(
        f'URL {repr(url)} scheme does not start with one of {VALID_COMFY_API_SCHEMES}'
    )
  if url_pr.path != '':
    raise ValueError(f'URL {repr(url)} path must be empty')

  if any_api_targets is not None:
    if url not in any_api_targets:
      raise ValueError(f'URL {repr(url)} is not one of {any_api_targets}')

  return url


def _ValidateComfySchemeURL(url: str, *, any_bases: List[str] | None) -> str:
  url_pr = ToParseResult(url=url)
  if url_pr.scheme not in VALID_COMFY_SCHEME_SCHEMES:
    raise ValueError(
        f'URL {repr(url)} scheme does not start with one of {VALID_COMFY_SCHEME_SCHEMES}'
    )

  # TODO: check the path

  if any_bases is not None:
    return ValidateIsBasedURL(url=url, any_bases=any_bases)
  return url


def ComfySchemeURLToTriplet(url: str,
                            *,
                            inversion_check: bool = __debug__
                            ) -> ComfyUIPathTriplet:
  """Turns a custom URL scheme into a triplet.

  Args:
      url (str): URL in the form of:
        comfy+http://comfy-server-host:port/folder_type/subfolder/sub/filename
  Raises:
      ValueError: When something is wrong with the URL.

  Returns:
      ComfyUIPathTriplet: The triplet.
  """
  url_pr = ToParseResult(url=url)
  url_path = url_pr.path

  if url_pr.scheme not in ['comfy+http', 'comfy+https']:
    raise ValueError(
        f'URL {repr(url)} does not start with one of {VALID_COMFY_SCHEME_SCHEMES}'
    )

  api_scheme = url_pr.scheme[6:]

  if not url_path.startswith('/'):
    raise ValueError(
        f'URL {url}, path {repr(url_path)} must start with a slash')

  # /folder_type/subfolder/filename => ('folder_type', 'subfolder', 'filename')
  # /folder_type/filename => ('folder_type', '', 'filename')
  # /folder_type/subfolder/subsubfolder/filename => ('folder_type', 'subfolder/subsubfolder', 'filename')
  # /folder_type//subfolder/subsubfolder/filename => ('folder_type', '/subfolder/subsubfolder', 'filename')
  # /folder_type/subfolder/subsubfolder//filename => ('folder_type', 'subfolder/subsubfolder/', 'filename')

  folder_type, _, rest = url_path[1:].partition('/')
  if folder_type not in VALID_FOLDER_TYPES:
    raise ValueError(
        f'URL {repr(url)} path {repr(url_path)} does not start with one of {VALID_FOLDER_TYPES}'
    )
  subfolder, _, filename = rest.rpartition('/')

  comfy_api_url_pr = url_pr._replace(scheme=api_scheme, path='')

  triplet = ComfyUIPathTriplet(comfy_api_url=comfy_api_url_pr.geturl(),
                               folder_type=folder_type,
                               subfolder=subfolder,
                               filename=filename)
  if inversion_check:
    inverted_url = TripletToComfySchemeURL(triplet=triplet,
                                           inversion_check=False)
    if inverted_url != url:
      raise ValueError(
          f'\nurl: {repr(url)}\ntriplet: {repr(triplet)}\ninverted_url: {repr(inverted_url)}'
      )
  return triplet


def TripletToComfySchemeURL(triplet: ComfyUIPathTriplet,
                            *,
                            inversion_check: bool = __debug__) -> str:
  comfy_api_url = ValidateIsComfyAPITargetURL(triplet.comfy_api_url)
  comfy_api_url_pr = ToParseResult(comfy_api_url)
  api_scheme = comfy_api_url_pr.scheme
  # ComfyUIPathTriplet validation should have already caught this.
  # trunk-ignore(bandit/B101)
  assert api_scheme in VALID_COMFY_API_SCHEMES
  # ComfyUIPathTriplet validation should have already caught this.
  # trunk-ignore(bandit/B101)
  assert triplet.folder_type in VALID_FOLDER_TYPES
  # ComfyUIPathTriplet validation should have already caught this.
  # trunk-ignore(bandit/B101)
  assert '/' not in triplet.filename
  # ComfyUIPathTriplet validation should have already caught this.
  # trunk-ignore(bandit/B101)
  assert triplet.filename != ''
  # ComfyUIPathTriplet validation should have already caught this.
  # trunk-ignore(bandit/B101)
  assert not triplet.subfolder.startswith('/')

  path = f'{triplet.folder_type}/{triplet.subfolder}'
  if not path.endswith('/'):
    path += '/'

  path = SmartURLJoin(path, triplet.filename)
  comfy_scheme = f'comfy+{ToParseResult(triplet.comfy_api_url).scheme}'
  # Sanity check, since api_scheme is in VALID_COMFY_API_SCHEMES, this should
  # always be true.
  # trunk-ignore(bandit/B101)
  assert comfy_scheme in VALID_COMFY_SCHEME_SCHEMES

  url_pr = comfy_api_url_pr._replace(scheme=comfy_scheme,
                                     path=SmartURLJoin(comfy_api_url_pr.path,
                                                       path))
  url = url_pr.geturl()
  # if inversion_check:
  #   inverted_triplet = _ComfySchemeURLToTriplet(url=url, inversion_check=False)
  #   assert inverted_triplet.Normalized() == triplet.Normalized(), (
  #       f'\ntriplet:                       {repr(triplet)}'
  #       f'\ntriplet.Normalized():          {repr(triplet.Normalized())}'
  #       f'\nurl:                           {repr(url)}'
  #       f'\ninverted_triplet:              {repr(inverted_triplet)}'
  #       f'\ninverted_triplet.Normalized(): {repr(inverted_triplet.Normalized())}'
  #   )

  return url


class ComfySchemeRemoteFileAPI(RemoteFileAPIBase):
  """This downloads and uploads files from the ComfyUI API directly.

  Uses the /view and /upload API endpoints.

  Maps comfy+http://comfy_host:port/folder_type/subfolder/filename to the
  endpoints.
  """

  def __init__(self, *, comfy_api_urls: List[str] | None, overwrite: bool):
    """Upload and download files from the ComfyUI API directly.

    Args:
        comfy_api_urls (str): The URL to the ComfyUI API, e.g
          http://127.0.0.1:8188. This is used for blacklisting any other
          attempts at upload or download. If None, then any URL is allowed to be
          uploaded or downloaded.
        overwrite (bool): If a file already exists, should it be overwritten? If
          false, the server will rename the file to something else and return
          that file name.
    """
    super().__init__()
    self._comfy_api_urls: List[str] | None = None
    if comfy_api_urls is not None:
      self._comfy_api_urls = [
          _ValidateComfyAPITargetURL(url, any_api_targets=None)
          for url in comfy_api_urls
      ]

    self._overwrite = overwrite

  def _ToTrustedTriplet(self, *,
                        untrusted_comfy_scheme_url: str) -> ComfyUIPathTriplet:
    triplet = ComfySchemeURLToTriplet(url=untrusted_comfy_scheme_url)
    return ComfyUIPathTriplet(comfy_api_url=_ValidateComfyAPITargetURL(
        triplet.comfy_api_url, any_api_targets=self._comfy_api_urls),
                              folder_type=triplet.folder_type,
                              subfolder=triplet.subfolder,
                              filename=triplet.filename)

  def _ValidateTriplet(
      self, *, untrusted_triplet: ComfyUIPathTriplet) -> ComfyUIPathTriplet:
    return ComfyUIPathTriplet(comfy_api_url=_ValidateComfyAPITargetURL(
        untrusted_triplet.comfy_api_url, any_api_targets=self._comfy_api_urls),
                              folder_type=untrusted_triplet.folder_type,
                              subfolder=untrusted_triplet.subfolder,
                              filename=untrusted_triplet.filename)

  async def DownloadFile(self, *, untrusted_src_url: str, dst_path: Path):
    trusted_src_triplet = self._ToTrustedTriplet(
        untrusted_comfy_scheme_url=untrusted_src_url)
    await self.DownloadTriplet(untrusted_src_triplet=trusted_src_triplet,
                               dst_path=dst_path)

  async def UploadFile(self, *, src_path: Path, untrusted_dst_url: str) -> str:
    # Validate andt turn the URL into the form:
    #   comfy+http://api_host:port/folder_type/subfolder/filename
    trusted_dst_triplet = self._ToTrustedTriplet(
        untrusted_comfy_scheme_url=untrusted_dst_url)
    new_triplet = await self.UploadToTriplet(
        src_path=src_path, untrusted_dst_triplet=trusted_dst_triplet)
    # Turn the triplet back into the form:
    #   comfy+http://api_host:port/folder_type/subfolder/filename
    return TripletToComfySchemeURL(triplet=new_triplet)

  async def DownloadTriplet(self, *, untrusted_src_triplet: ComfyUIPathTriplet,
                            dst_path: Path):
    trusted_src_triplet = self._ValidateTriplet(
        untrusted_triplet=untrusted_src_triplet)

    async with ComfyAPIClient(
        comfy_api_url=trusted_src_triplet.comfy_api_url) as client:
      data: bytes = await client.GetView(
          folder_type=trusted_src_triplet.folder_type,
          subfolder=trusted_src_triplet.subfolder,
          filename=trusted_src_triplet.filename)

    await dst_path.parent.mkdir(parents=True, exist_ok=True)
    async with await dst_path.open('wb') as f:
      await f.write(data)

  async def UploadToTriplet(
      self, *, src_path: Path,
      untrusted_dst_triplet: ComfyUIPathTriplet) -> ComfyUIPathTriplet:
    trusted_dst_triplet = self._ValidateTriplet(
        untrusted_triplet=untrusted_dst_triplet)

    async with await src_path.open('rb') as f:
      data = await f.read()

    async with ComfyAPIClient(
        comfy_api_url=trusted_dst_triplet.comfy_api_url) as client:
      resp: APIUploadImageResp = await client.PostUploadImage(
          folder_type=trusted_dst_triplet.folder_type,
          subfolder=trusted_dst_triplet.subfolder,
          filename=trusted_dst_triplet.filename,
          data=data,
          overwrite=self._overwrite)
    # If the server renamed the file, we need to update the triplet.
    return trusted_dst_triplet.model_copy(update={
        'filename': resp.name,
        'subfolder': resp.subfolder,
        'folder_type': resp.type
    },
                                          deep=True)

  def TripletToURL(self, *, triplet: ComfyUIPathTriplet) -> str:
    return TripletToComfySchemeURL(triplet=triplet)

  def URLToTriplet(self, *, url: str) -> ComfyUIPathTriplet:
    return ComfySchemeURLToTriplet(url=url)

  def GetBases(self) -> list[str]:
    if self._comfy_api_urls is None:
      return [f'comfy+{scheme}://' for scheme in VALID_COMFY_API_SCHEMES]

    return [
        ParseResult(scheme=f'comfy+{url_pr.scheme}',
                    netloc=url_pr.netloc,
                    path='',
                    params='',
                    query='',
                    fragment='').geturl()
        for url_pr in map(ToParseResult, self._comfy_api_urls)
    ]
