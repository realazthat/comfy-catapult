# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT
#
# The Comfy Catapult project requires contributions made to this file be licensed
# under the MIT license or a compatible open source license. See LICENSE.md for
# the license text.

import json
from typing import List, Optional, Tuple, cast
from urllib.parse import ParseResult

from anyio import Path
from typing_extensions import Literal

from ._internal.url_utils import (VALID_COMFY_API_SCHEMES, SmartURLJoin,
                                  ToParseResult, ValidateIsBasedURL,
                                  ValidateIsComfyAPITargetURL)
from .api_client import ComfyAPIClient
from .comfy_schema import (VALID_FOLDER_TYPES, APIUploadImageResp,
                           ComfyUIPathTriplet)
from .remote_file_api_base import RemoteFileAPIBase

VALID_COMFY_SCHEME_SCHEMES = ['comfy+http', 'comfy+https']


def _ValidateComfyAPITargetURL(url: str, *,
                               any_api_targets: Optional[List[str]]) -> str:
  url_pr = ToParseResult(url=url)
  if url_pr.scheme not in VALID_COMFY_API_SCHEMES:
    raise ValueError(
        f'URL {json.dumps(url)} scheme does not start with one of {VALID_COMFY_API_SCHEMES}'
    )

  if any_api_targets is not None:
    if url not in any_api_targets:
      raise ValueError(f'URL {json.dumps(url)} is not one of {any_api_targets}')

  return url


def _ValidateComfySchemeURL(url: str, *, any_bases: Optional[List[str]]) -> str:
  url_pr = ToParseResult(url=url)
  if url_pr.scheme not in VALID_COMFY_SCHEME_SCHEMES:
    raise ValueError(
        f'URL {json.dumps(url)} scheme does not start with one of {VALID_COMFY_SCHEME_SCHEMES}'
    )

  # TODO: check the path

  if any_bases is not None:
    return ValidateIsBasedURL(url=url, any_bases=any_bases)
  return url


def ComfySchemeURLToTriplet(
    url: str,
    *,
    inversion_check: bool = __debug__) -> Tuple[str, ComfyUIPathTriplet]:
  """Turns a custom URL scheme into a triplet.

  Args:
    url (str): URL in the form of:
      comfy+http://comfy-server-host:port/folder_type/subfolder/sub/filename
  Raises:
    ValueError: When something is wrong with the URL.

  Returns:
    Tuple[str, ComfyUIPathTriplet]: The ComfyUI API URL, and the triplet.
  """
  url_pr = ToParseResult(url=url)
  url_path: str = url_pr.path

  if url_pr.scheme not in ['comfy+http', 'comfy+https']:
    raise ValueError(
        f'URL {json.dumps(url)} does not start with one of {VALID_COMFY_SCHEME_SCHEMES}'
    )

  api_scheme = url_pr.scheme[6:]

  if not url_path.startswith('/'):
    raise ValueError(
        f'URL {url}, path {json.dumps(url_path)} must start with a slash')

  # /folder_type/subfolder/filename => ('folder_type', 'subfolder', 'filename')
  # /folder_type/filename => ('folder_type', '', 'filename')
  # /folder_type/subfolder/subsubfolder/filename => ('folder_type', 'subfolder/subsubfolder', 'filename')
  # /folder_type//subfolder/subsubfolder/filename => ('folder_type', '/subfolder/subsubfolder', 'filename')
  # /folder_type/subfolder/subsubfolder//filename => ('folder_type', 'subfolder/subsubfolder/', 'filename')

  folder_type_str: str
  folder_type_str, _, rest = url_path[1:].partition('/')
  if folder_type_str not in VALID_FOLDER_TYPES:
    raise ValueError(
        f'URL {json.dumps(url)} path {json.dumps(url_path)} does not start with one of {VALID_FOLDER_TYPES}'
    )
  folder_type = cast(Literal['input', 'output', 'temp'], folder_type_str)
  subfolder, _, filename = rest.rpartition('/')

  comfy_api_url_pr = url_pr._replace(scheme=api_scheme, path='')

  triplet = ComfyUIPathTriplet(type=folder_type,
                               subfolder=subfolder,
                               filename=filename)
  if inversion_check:
    inverted_url = TripletToComfySchemeURL(
        comfy_api_url=comfy_api_url_pr.geturl(),
        triplet=triplet,
        inversion_check=False)
    if inverted_url != url:
      raise ValueError(
          f'\nurl: {json.dumps(url)}\ntriplet: {repr(triplet)}\ninverted_url: {json.dumps(inverted_url)}'
      )
  return comfy_api_url_pr.geturl(), triplet


def TripletToComfySchemeURL(comfy_api_url: str,
                            triplet: ComfyUIPathTriplet,
                            *,
                            inversion_check: bool = __debug__) -> str:
  comfy_api_url = ValidateIsComfyAPITargetURL(comfy_api_url)
  comfy_api_url_pr = ToParseResult(comfy_api_url)
  api_scheme = comfy_api_url_pr.scheme
  # ComfyUIPathTriplet validation should have already caught this.
  # trunk-ignore(bandit/B101)
  assert api_scheme in VALID_COMFY_API_SCHEMES
  # ComfyUIPathTriplet validation should have already caught this.
  # trunk-ignore(bandit/B101)
  assert triplet.type in VALID_FOLDER_TYPES
  # ComfyUIPathTriplet validation should have already caught this.
  # trunk-ignore(bandit/B101)
  assert '/' not in triplet.filename
  # ComfyUIPathTriplet validation should have already caught this.
  # trunk-ignore(bandit/B101)
  assert triplet.filename != ''
  # ComfyUIPathTriplet validation should have already caught this.
  # trunk-ignore(bandit/B101)
  assert not triplet.subfolder.startswith('/')

  path = triplet.ToLocalPathStr(include_folder_type=True)
  comfy_scheme = f'comfy+{ToParseResult(comfy_api_url).scheme}'
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
  #       f'\nurl:                           {json.dumps(url)}'
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

  def __init__(self, *, comfy_api_urls: Optional[List[str]], overwrite: bool):
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
    self._comfy_api_urls: Optional[List[str]] = None
    if comfy_api_urls is not None:
      self._comfy_api_urls = [
          _ValidateComfyAPITargetURL(url, any_api_targets=None)
          for url in comfy_api_urls
      ]

    self._overwrite = overwrite

  def _ToTrustedTriplet(
      self, *,
      untrusted_comfy_scheme_url: str) -> Tuple[str, ComfyUIPathTriplet]:
    comfy_api_url, triplet = ComfySchemeURLToTriplet(
        url=untrusted_comfy_scheme_url)
    comfy_api_url = _ValidateComfyAPITargetURL(
        comfy_api_url, any_api_targets=self._comfy_api_urls)
    return comfy_api_url, triplet

  def _ValidateTriplet(
      self, *, untrusted_comfy_api_url: str,
      untrusted_triplet: ComfyUIPathTriplet) -> Tuple[str, ComfyUIPathTriplet]:
    comfy_api_url = _ValidateComfyAPITargetURL(
        untrusted_comfy_api_url, any_api_targets=self._comfy_api_urls)
    triplet = untrusted_triplet
    return comfy_api_url, triplet

  async def DownloadFile(self, *, untrusted_src_url: str, dst_path: Path):
    trusted_comfy_api_url, trusted_src_triplet = self._ToTrustedTriplet(
        untrusted_comfy_scheme_url=untrusted_src_url)
    await self.DownloadTriplet(untrusted_comfy_api_url=trusted_comfy_api_url,
                               untrusted_src_triplet=trusted_src_triplet,
                               dst_path=dst_path)

  async def UploadFile(self, *, src_path: Path, untrusted_dst_url: str) -> str:
    # Validate andt turn the URL into the form:
    #   comfy+http://api_host:port/folder_type/subfolder/filename
    trusted_comfy_api_url, trusted_dst_triplet = self._ToTrustedTriplet(
        untrusted_comfy_scheme_url=untrusted_dst_url)
    new_triplet = await self.UploadToTriplet(
        src_path=src_path,
        untrusted_comfy_api_url=trusted_comfy_api_url,
        untrusted_dst_triplet=trusted_dst_triplet)
    # Turn the triplet back into the form:
    #   comfy+http://api_host:port/folder_type/subfolder/filename
    return TripletToComfySchemeURL(comfy_api_url=trusted_comfy_api_url,
                                   triplet=new_triplet)

  async def DownloadTriplet(self, *, untrusted_comfy_api_url: str,
                            untrusted_src_triplet: ComfyUIPathTriplet,
                            dst_path: Path):
    trusted_comfy_api_url, trusted_src_triplet = self._ValidateTriplet(
        untrusted_comfy_api_url=untrusted_comfy_api_url,
        untrusted_triplet=untrusted_src_triplet)

    async with ComfyAPIClient(comfy_api_url=trusted_comfy_api_url) as client:
      data: bytes = await client.GetView(
          folder_type=trusted_src_triplet.type,
          subfolder=trusted_src_triplet.subfolder,
          filename=trusted_src_triplet.filename)

    await dst_path.parent.mkdir(parents=True, exist_ok=True)
    async with await dst_path.open('wb') as f:
      await f.write(data)

  async def UploadToTriplet(
      self, *, src_path: Path, untrusted_comfy_api_url: str,
      untrusted_dst_triplet: ComfyUIPathTriplet) -> ComfyUIPathTriplet:
    trusted_comfy_api_url, trusted_dst_triplet = self._ValidateTriplet(
        untrusted_comfy_api_url=untrusted_comfy_api_url,
        untrusted_triplet=untrusted_dst_triplet)

    async with await src_path.open('rb') as f:
      data = await f.read()

    async with ComfyAPIClient(comfy_api_url=trusted_comfy_api_url) as client:
      resp: APIUploadImageResp = await client.PostUploadImage(
          folder_type=trusted_dst_triplet.type,
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

  def TripletToURL(self, *, comfy_api_url: str,
                   triplet: ComfyUIPathTriplet) -> str:
    return TripletToComfySchemeURL(comfy_api_url=comfy_api_url, triplet=triplet)

  def URLToTriplet(self, *, url: str) -> Tuple[str, ComfyUIPathTriplet]:
    return ComfySchemeURLToTriplet(url=url)

  def GetBases(self) -> List[str]:
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
