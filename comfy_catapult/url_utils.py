# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT
#
# The Comfy Catapult project requires contributions made to this file be licensed
# under the MIT license or a compatible open source license. See LICENSE.md for
# the license text.

from typing import List, Literal
from urllib.parse import ParseResult, urljoin, urlparse, urlunparse

from pydantic import BaseModel, ConfigDict, field_validator

from comfy_catapult.errors import (BasedURLValidationError,
                                   URLDirectoryValidationError,
                                   URLValidationError)

ComfyFolderType = Literal['input', 'output', 'temp']
ComfyAPIScheme = Literal['http', 'https']
VALID_COMFY_API_SCHEMES: List[ComfyAPIScheme] = ['http', 'https']
VALID_FOLDER_TYPES: List[ComfyFolderType] = ['input', 'output', 'temp']


def SmartURLJoin(base: str, path: str) -> str:
  """urljoin() but can handle relative paths even for custom schemes.

  See: https://github.com/python/cpython/issues/63028

  From: https://github.com/python/cpython/issues/63028#issuecomment-1564858715
  """
  parsed_base = urlparse(base)
  new = parsed_base._replace(path=urljoin(parsed_base.path, path))
  return urlunparse(new)


def IsValidURL(url: str) -> bool:
  try:
    urlparse(url)
    return True
  except ValueError:
    return False


def ToParseResult(url: str) -> ParseResult:
  try:
    return urlparse(url)
  except ValueError as e:
    raise URLValidationError(f'URL {repr(url)} is not valid: {e}') from e


def ValidateIsURL(url: str) -> str:
  if not IsValidURL(url=url):
    raise URLValidationError(f'URL {repr(url)} is not valid')
  return url


def IsWeaklyRelativeTo(*, base: str, url: str) -> bool:
  url = ValidateIsURL(url=url)
  base = ValidateIsURL(url=base)
  base_parsed = ToParseResult(url=base)
  joined = SmartURLJoin(base, url)
  joined_parsed = ToParseResult(url=joined)

  if (base_parsed.scheme, base_parsed.netloc) != (joined_parsed.scheme,
                                                  joined_parsed.netloc):
    return False

  return joined_parsed.path.startswith(base_parsed.path)


def ValidateIsBasedURL(*, url: str, any_bases: List[str]) -> str:
  url = ValidateIsURL(url=url)

  for base in any_bases:
    base = ValidateIsURL(url=base)
    if IsWeaklyRelativeTo(base=base, url=url):
      return url
  raise BasedURLValidationError(
      f'URL {repr(url)} is not relative to any of {any_bases}')


def Relativize(*, base: str, url: str) -> str:
  """Return the relative path from base to url, as a valid relative URL.

  """
  url = ValidateIsURL(url=url)
  base = ValidateIsURL(url=base)
  url = ValidateIsBasedURL(url=url, any_bases=[base])

  url_parsed = ToParseResult(url=url)
  base_parsed = ToParseResult(url=base)

  url_path = url_parsed.path
  base_path = base_parsed.path
  assert url_path.startswith(base_path)

  return url_path[len(base_path):]


def ValidateIsURLDirectory(url: str) -> str:
  url = ValidateIsURL(url=url)
  url_pr: ParseResult = ToParseResult(url=url)
  if not url_pr.path.endswith('/'):
    raise URLDirectoryValidationError(
        f'URL {repr(url)} is not a directory, because it does not end with a trailing slash'
    )
  return url


def ValidateIsComfyAPITargetURL(url: str) -> str:
  url_pr: ParseResult = ToParseResult(url=url)
  if url_pr.scheme not in VALID_COMFY_API_SCHEMES:
    raise ValueError(f'URL {repr(url)} is not a comfy API target URL, because'
                     f' its scheme is not one of {VALID_COMFY_API_SCHEMES}')
  if url_pr.hostname is None or url_pr.hostname == '':
    raise ValueError(f'URL {repr(url)} is not a comfy API target URL, because'
                     f' its hostname is empty')

  return url


class ComfyUIPathTriplet(BaseModel):
  """
  Represents a folder_type/subfolder/filename triplet, which ComfyUI API and
  some nodes use as file paths.
  """
  model_config = ConfigDict(frozen=True)

  comfy_api_url: str
  folder_type: ComfyFolderType
  subfolder: str
  filename: str

  @field_validator('comfy_api_url')
  @classmethod
  def validate_comfy_api_url(cls, v: str):
    v = ValidateIsComfyAPITargetURL(url=v)
    return v

  @field_validator('folder_type')
  @classmethod
  def validate_folder_type(cls, v: str):
    if v not in VALID_FOLDER_TYPES:
      raise ValueError(
          f'folder_type {repr(v)} is not one of {VALID_FOLDER_TYPES}')
    return v

  @field_validator('subfolder')
  @classmethod
  def validate_subfolder(cls, v: str):
    if v.startswith('/'):
      raise ValueError(f'subfolder {repr(v)} must not start with a slash')
    return v

  @field_validator('filename')
  @classmethod
  def validate_filename(cls, v: str):
    if '/' in v:
      raise ValueError(f'filename {repr(v)} must not contain a slash')
    if v == '':
      raise ValueError(f'filename {repr(v)} must not be empty')
    return v

  def ToLocalPathStr(self, *, include_folder_type: bool) -> str:
    """Converts this triplet to something like `input/subfolder/filename`.
    """
    subfolder = self.subfolder
    if subfolder == '':
      subfolder = '.'
    if not subfolder.endswith('/'):
      subfolder += '/'

    local_path = urljoin(subfolder, self.filename)
    if include_folder_type:
      local_path = urljoin(f'{self.folder_type}/', local_path)
    return local_path

  # def Normalized(self) -> 'ComfyUIPathTriplet':
  #   subfolder_url = ToParseResult(url=self.subfolder)
  #   subfolder = subfolder_url.path
  #   subfolder = urljoin('', subfolder)
  #   if subfolder.endswith('/'):
  #     subfolder = subfolder[:-1]
  #   if subfolder.startswith('./'):
  #     subfolder = subfolder[2:]

  #   return ComfyUIPathTriplet(comfy_api_url=self.comfy_api_url,
  #                             folder_type=self.folder_type,
  #                             subfolder=subfolder,
  #                             filename=self.filename)
