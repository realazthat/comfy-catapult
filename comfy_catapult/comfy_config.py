# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT
#
# The Comfy Catapult project require contributions made to this file be licensed
# under the MIT license or a compatible open source license. See LICENSE.md for
# the license text.

from pydantic import BaseModel, field_validator

from comfy_catapult.url_utils import ToParseResult, ValidateIsURLDirectory


class RemoteComfyConfig(BaseModel):
  """
  TODO: is this class still needed?
  """
  comfy_api_url: str
  base_file_url: str
  """Optional URL to ComfyUI install directory, e.g.'file:///mnt/d/stability-matrix-data/Packages/ComfyUI/'.

  Note, that the URL must end with a trailing slash, or be empty.

  If empty, then the ComfyUI API will be used to transfer files.
  """
  input_file_url: str
  output_file_url: str
  temp_file_url: str

  @field_validator('base_file_url', 'input_file_url', 'output_file_url',
                   'temp_file_url')
  @classmethod
  def val_base_url(cls, v: str):
    return ValidateIsURLDirectory(url=v)

  @field_validator('base_file_url', 'input_file_url', 'output_file_url',
                   'temp_file_url')
  @classmethod
  def val_file_url(cls, v: str):
    url = ToParseResult(url=v)
    if url.scheme != 'file':
      raise ValueError(f'URL {repr(v)} is not a file:// URL')
    return v

  @field_validator('base_file_url', 'input_file_url', 'output_file_url',
                   'temp_file_url')
  @classmethod
  def val_abs_url(cls, v: str):
    url = ToParseResult(url=v)
    if not url.path.startswith('/'):
      raise ValueError(f'URL {repr(v)} is not an absolute URL')
    return v
