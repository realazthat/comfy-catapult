# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT
#
# The Catapult require contributions made to this file be licensed under the MIT
# license or a compatible open source license. See LICENSE.md for the license
# text.

import argparse
import os
import sys
import traceback
from typing import NamedTuple
from urllib.parse import ParseResult, urlparse

from anyio import Path

from comfy_catapult.url_utils import SmartURLJoin, ValidateIsURLDirectory


class Args(NamedTuple):
  comfy_api_url: str
  api_workflow_json_path: Path
  comfy_base_file_url: str
  comfy_input_file_url: str
  comfy_temp_file_url: str
  comfy_output_file_url: str
  tmp_path: Path
  output_path: Path

  ckpt_name: str | None
  positive_prompt: str
  negative_prompt: str


async def ParseArgs() -> Args:

  def URL_HELP(to: str, example_url: str, default_subdir: str | None):
    lines = [
        f'Optional URL to ComfyUI {to} directory, e.g. {repr(example_url)}.',
        'Note, that the URL must end with a trailing slash.',
        'If --comfy_base_file_url is not supplied or is empty, then the API will be used to transfer files.',
    ]
    if default_subdir is not None:
      lines += [f"Defaults to comfy_base_file_url + '{default_subdir}'."]
    return ' '.join(lines)

  parser = argparse.ArgumentParser()
  parser.add_argument('--comfy_api_url', type=urlparse, default=None)
  parser.add_argument('--api_workflow_json_path',
                      type=Path,
                      default=Path('./test_data/sdxlturbo_example_api.json'))
  parser.add_argument(
      '--comfy_base_file_url',
      type=urlparse,
      default=None,
      help=URL_HELP('install',
                    'file:///mnt/d/stability-matrix-data/Packages/ComfyUI/',
                    None))

  parser.add_argument(
      '--comfy_input_file_url',
      type=urlparse,
      default=None,
      help=URL_HELP(
          'input',
          'file:///mnt/d/stability-matrix-data/Packages/ComfyUI/input/',
          'input/'))
  parser.add_argument(
      '--comfy_output_file_url',
      type=urlparse,
      default=None,
      help=URL_HELP(
          'output',
          'file:///mnt/d/stability-matrix-data/Packages/ComfyUI/output/',
          'output/'))
  parser.add_argument(
      '--comfy_temp_file_url',
      type=urlparse,
      default=None,
      help=URL_HELP(
          'output',
          'file:///mnt/d/stability-matrix-data/Packages/ComfyUI/temp/',
          'output/'))
  parser.add_argument('--tmp_path', type=Path, required=True)
  parser.add_argument('--output_path', type=Path, required=True)

  parser.add_argument('--ckpt_name', type=str, default=None)
  parser.add_argument('--positive_prompt', type=str, required=True)
  parser.add_argument('--negative_prompt', type=str, required=True)

  args = parser.parse_args()

  ##############################################################################
  try:
    comfy_api_url_pr: ParseResult | None = args.comfy_api_url
    if comfy_api_url_pr is None:
      # Check if COMFY_API_URL is an environment variable.
      env_comfy_api_url: str | None = os.environ.get('COMFY_API_URL')
      if env_comfy_api_url is not None:
        comfy_api_url_pr = urlparse(env_comfy_api_url)
      else:
        parser.print_usage(file=sys.stderr)
        print(
            'Error: argument --comfy_api_url is required, unless COMFY_API_URL is set in the environment',
            file=sys.stderr)
        sys.exit(1)
    comfy_api_url: str = comfy_api_url_pr.geturl()
  except ValueError as e:
    print(f'Error: Failed parsing --comfy_api_url or COMFY_API_URL: {e}',
          file=sys.stderr)
    parser.print_usage(file=sys.stderr)
    traceback.print_exc(file=sys.stderr)
    raise
  ##############################################################################
  api_workflow_json_path: Path = args.api_workflow_json_path
  ##############################################################################
  comfy_base_file_url_pr: ParseResult | None = args.comfy_base_file_url

  comfy_input_file_url_pr: ParseResult | None = args.comfy_input_file_url
  comfy_output_file_url_pr: ParseResult | None = args.comfy_output_file_url
  comfy_temp_file_url_pr: ParseResult | None = args.comfy_temp_file_url
  if comfy_base_file_url_pr is None or comfy_base_file_url_pr.geturl() == '':
    comfy_base_file_url_pr = urlparse(ValidateIsURLDirectory(url='file:///'))
  comfy_api_url_pr = urlparse(
      ValidateIsURLDirectory(url=comfy_base_file_url_pr.geturl()))

  if comfy_input_file_url_pr is None:
    comfy_input_file_url_pr = urlparse(
        SmartURLJoin(comfy_base_file_url_pr.geturl(), 'input/'))
  if comfy_output_file_url_pr is None:
    comfy_output_file_url_pr = urlparse(
        SmartURLJoin(comfy_base_file_url_pr.geturl(), 'output/'))
  if comfy_temp_file_url_pr is None:
    comfy_temp_file_url_pr = urlparse(
        SmartURLJoin(comfy_base_file_url_pr.geturl(), 'temp/'))

  comfy_base_file_url = comfy_base_file_url_pr.geturl()
  comfy_input_file_url = comfy_input_file_url_pr.geturl()
  comfy_output_file_url = comfy_output_file_url_pr.geturl()
  comfy_temp_file_url = comfy_temp_file_url_pr.geturl()
  ##############################################################################
  tmp_path: Path = args.tmp_path
  ##############################################################################
  output_path: Path = args.output_path
  ##############################################################################

  return Args(
      comfy_api_url=comfy_api_url,
      api_workflow_json_path=api_workflow_json_path,
      comfy_base_file_url=comfy_base_file_url,
      comfy_input_file_url=comfy_input_file_url,
      comfy_output_file_url=comfy_output_file_url,
      comfy_temp_file_url=comfy_temp_file_url,
      tmp_path=tmp_path,
      output_path=output_path,
      ckpt_name=args.ckpt_name,
      positive_prompt=args.positive_prompt,
      negative_prompt=args.negative_prompt,
  )
