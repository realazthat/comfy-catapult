# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT
#
# The Comfy Catapult project requires contributions made to this file be licensed
# under the MIT license or a compatible open source license. See LICENSE.md for
# the license text.

import json
import os
import unittest
import uuid
from typing import Dict, Optional
from urllib.parse import urlparse

from anyio import Path
from websockets import connect

from .catapult import _BasicAuthToHeaders, _GetWebSocketURL
from .comfy_schema import WSMessage
from .comfy_utils import TryParseAsModel

COMFY_API_URL = os.environ.get('COMFY_API_URL')
if COMFY_API_URL is None:
  raise ValueError('Please set COMFY_API_URL in the environment')


class CatapultTest(unittest.IsolatedAsyncioTestCase):

  async def asyncSetUp(self):
    if COMFY_API_URL is None:
      raise ValueError('Please set COMFY_API_URL in the environment')
    self._comfy_api_url: str = COMFY_API_URL
    self._job_debug_path: Optional[Path] = None
    job_debug_path: Optional[str] = os.environ.get('JOB_DEBUG_PATH')
    if job_debug_path is not None:
      self._job_debug_path = Path(job_debug_path)

  async def test_WSBasicAuth(self):
    errors_dump_directory: Optional[Path] = None
    if self._job_debug_path is not None:
      errors_dump_directory = self._job_debug_path / 'errors'

    client_id = str(uuid.uuid4())
    ws_url = urlparse(
        _GetWebSocketURL(comfy_api_url=self._comfy_api_url,
                         client_id=client_id))

    ws_headers: Dict[str, str] = {}
    ws_url = urlparse(
        _BasicAuthToHeaders(url=ws_url.geturl(), headers=ws_headers))

    print(f'ws_url: {ws_url.geturl()}')
    async with connect(ws_url.geturl(), extra_headers=ws_headers) as ws:
      while True:
        out = await ws.recv()
        if not isinstance(out, str):
          continue
        message = await TryParseAsModel(
            content=json.loads(out),
            model_type=WSMessage,
            errors_dump_directory=errors_dump_directory)
        print(message)
        return


if __name__ == '__main__':
  unittest.main()
