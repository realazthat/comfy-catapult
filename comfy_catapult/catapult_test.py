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
from typing import Dict, List, Optional
from unittest.mock import AsyncMock
from urllib.parse import urlparse

import aiofiles
from anyio import Path
from websockets import connect

from ._internal.utilities import (BasicAuthToHeaders, GetWebSocketURL,
                                  TryParseAsModel)
from .api_client import ComfyAPIClient
from .catapult import ComfyCatapult
from .catapult_base import JobStatus
from .comfy_schema import APIWorkflow, WSMessage
from .comfy_utils import GetNodeByTitle

COMFY_API_URL = os.environ.get('COMFY_API_URL')
if COMFY_API_URL is None:
  raise ValueError('Please set COMFY_API_URL in the environment')


class StrictMock(AsyncMock):

  def __getattr__(self, name):
    if name in self.__dict__:
      return super().__getattr__(name)
    raise AttributeError(f"Mock object has no attribute '{name}'")


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
    """
    This test is assumes that COMFY_API_URL is a basic auth URL. Otherwise, it
    does not actually test anything useful.
    """
    errors_dump_directory: Optional[Path] = None
    if self._job_debug_path is not None:
      errors_dump_directory = self._job_debug_path / 'errors'

    client_id = str(uuid.uuid4())
    ws_url = urlparse(
        GetWebSocketURL(comfy_api_url=self._comfy_api_url, client_id=client_id))

    ws_headers: Dict[str, str] = {}
    ws_url = urlparse(
        BasicAuthToHeaders(url=ws_url.geturl(), headers=ws_headers))

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

  async def test_Resume(self):
    async with aiofiles.open('test_data/default_workflow_api.json', 'r') as f:
      prepared_workflow_dict = json.loads(await f.read())

    prepared_workflow = APIWorkflow.model_validate(prepared_workflow_dict)
    _, ksampler_node = GetNodeByTitle(workflow=prepared_workflow,
                                      title='KSampler')
    # Make this 100 so we have time to resume the job.
    ksampler_node.inputs['steps'] = 100

    job_id = str(uuid.uuid4())
    errors: List[Exception] = []

    async with ComfyAPIClient(
        comfy_api_url=self._comfy_api_url) as comfy_client:
      async with ComfyCatapult(comfy_client=comfy_client,
                               debug_path=None) as catapult:
        job_status: JobStatus
        job_status, _ = await catapult.Catapult(
            job_id=job_id,
            prepared_workflow=prepared_workflow_dict,
            important=[],
            use_future_api=True)

        errors = await catapult.GetExceptions(job_id=job_id)

    async with ComfyAPIClient(
        comfy_api_url=self._comfy_api_url) as comfy_client:
      async with ComfyCatapult(comfy_client=comfy_client,
                               debug_path=None) as catapult:
        await catapult.Resume(job_id=job_id,
                              prepared_workflow=prepared_workflow_dict,
                              important=[],
                              status=job_status,
                              poll=True,
                              errors=errors)

        job_status, future = await catapult.GetStatus(job_id=job_id)
        await future


if __name__ == '__main__':
  unittest.main()
