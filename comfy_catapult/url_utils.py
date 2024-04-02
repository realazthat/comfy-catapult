# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT
#
# The Comfy Catapult project requires contributions made to this file be licensed
# under the MIT license or a compatible open source license. See LICENSE.md for
# the license text.

from typing import List, Literal
from urllib.parse import ParseResult, urljoin, urlparse, urlunparse

from comfy_catapult.errors import (BasedURLValidationError,
                                   URLDirectoryValidationError,
                                   URLValidationError)

ComfyAPIScheme = Literal['http', 'https']
VALID_COMFY_API_SCHEMES: List[ComfyAPIScheme] = ['http', 'https']


def SmartURLJoin(base: str, url: str) -> str:
  """urljoin() but can handle relative paths even for custom schemes.

  See: https://github.com/python/cpython/issues/63028

  From: https://github.com/python/cpython/issues/63028#issuecomment-1564858715
  """
  base_pr = urlparse(base)
  bscheme = base_pr.scheme

  url_pr = urlparse(url)
  scheme = url_pr.scheme or bscheme
  if bscheme != scheme:
    return url

  base_pr = base_pr._replace(scheme='http')
  url_pr = url_pr._replace(scheme='http')

  joined = urljoin(urlunparse(base_pr), urlunparse(url_pr))
  joined_pr = urlparse(joined)
  joined_pr = joined_pr._replace(scheme=scheme)
  return urlunparse(joined_pr)


def JoinToBaseURL(base: str, path: str) -> str:
  """Takes a URL and appends the path to it.
  
  Always assumes the base is a directory. Always assumes the path is relative to that directory."""
  if not base.endswith('/'):
    base += '/'
  if path.startswith('/'):
    path = path[1:]
  return base + path


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
  if not url_path.startswith(base_path):
    raise ValueError(f'URL {repr(url)} is not relative to base {repr(base)}')

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
