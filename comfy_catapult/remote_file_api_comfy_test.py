# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT
#
# The Comfy Catapult project requires contributions made to this file be licensed
# under the MIT license or a compatible open source license. See LICENSE.md for
# the license text.

import os
import unittest
from tempfile import TemporaryDirectory
from typing import List
from unittest import IsolatedAsyncioTestCase

import pydantic
from anyio import Path

from .comfy_schema import (VALID_FOLDER_TYPES, ComfyFolderType,
                           ComfyUIPathTriplet)
from .comfy_schema_test import VALID_SUBFOLDER_EDGES
from .remote_file_api_comfy import (ComfySchemeRemoteFileAPI,
                                    TripletToComfySchemeURL)
from .url_utils import SmartURLJoin

COMFY_API_URL = os.environ.get('COMFY_API_URL')
if COMFY_API_URL is None:
  raise ValueError('Please set COMFY_API_URL in the environment')


class TestRemoteFileApiComfy(IsolatedAsyncioTestCase):

  async def asyncSetUp(self):
    if COMFY_API_URL is None:
      raise ValueError('Please set COMFY_API_URL in the environment')
    self._comfy_api_url: str = COMFY_API_URL
    self._remote = ComfySchemeRemoteFileAPI(comfy_api_urls=[COMFY_API_URL],
                                            overwrite=True)

  async def asyncTearDown(self):
    pass

  async def _test_UploadFile(self, *, comfy_api_url: str,
                             triplet: ComfyUIPathTriplet):
    with TemporaryDirectory() as tmp_dir:
      path = Path(tmp_dir) / 'local-file.txt'
      local_download_path = Path(tmp_dir) / 'local-downloaded.txt'
      contents = 'hello world'
      await path.write_text(contents)

      input_url = TripletToComfySchemeURL(comfy_api_url=comfy_api_url,
                                          triplet=triplet)

      uploaded_url = await self._remote.UploadFile(src_path=path,
                                                   untrusted_dst_url=input_url)

      await self._remote.DownloadFile(untrusted_src_url=uploaded_url,
                                      dst_path=local_download_path)

      downloaded_contents = await local_download_path.read_text()
      self.assertEqual(contents, downloaded_contents)

  async def test_UploadFile(self):
    folder_type: ComfyFolderType
    folder_types: List[ComfyFolderType] = ['input']
    for folder_type in folder_types:
      for subfolder, _ in VALID_SUBFOLDER_EDGES:
        with self.subTest(folder_type=folder_type, subfolder=subfolder):
          await self._test_UploadFile(comfy_api_url=self._comfy_api_url,
                                      triplet=ComfyUIPathTriplet(
                                          type=folder_type,
                                          subfolder=subfolder,
                                          filename='remote-file.txt'))

  async def _test_UploadToTriplet(self, *, comfy_api_url: str,
                                  triplet: ComfyUIPathTriplet):
    with TemporaryDirectory() as tmp_dir:
      path = Path(tmp_dir) / 'local-file.txt'
      local_download_path = Path(tmp_dir) / 'local-downloaded.txt'
      contents = 'hello world'
      await path.write_text(contents)

      uploaded_triplet = await self._remote.UploadToTriplet(
          src_path=path,
          untrusted_comfy_api_url=comfy_api_url,
          untrusted_dst_triplet=triplet)

      await self._remote.DownloadTriplet(untrusted_comfy_api_url=comfy_api_url,
                                         untrusted_src_triplet=uploaded_triplet,
                                         dst_path=local_download_path)

      downloaded_contents = await local_download_path.read_text()
      self.assertEqual(contents, downloaded_contents)

  async def test_UploadToTriplet(self):
    folder_type: ComfyFolderType
    folder_types: List[ComfyFolderType] = ['input']
    for folder_type in folder_types:
      for subfolder, _ in VALID_SUBFOLDER_EDGES:
        with self.subTest(folder_type=folder_type, subfolder=subfolder):

          await self._test_UploadToTriplet(comfy_api_url=self._comfy_api_url,
                                           triplet=ComfyUIPathTriplet(
                                               type=folder_type,
                                               subfolder=subfolder,
                                               filename='remote-file.txt'))

  async def test__TripletToComfySchemeURL(self):
    comfy_api_url = 'http://comfy_host:23534/'
    comfy_scheme_url = 'comfy+http://comfy_host:23534/'

    self.assertEqual(
        TripletToComfySchemeURL(comfy_api_url=comfy_api_url,
                                triplet=ComfyUIPathTriplet(
                                    type='input',
                                    subfolder='',
                                    filename='remote-file.txt')),
        SmartURLJoin(comfy_scheme_url, 'input/remote-file.txt'))
    with self.assertRaises(pydantic.ValidationError):
      _ = ComfyUIPathTriplet(type='input',
                             subfolder='/',
                             filename='remote-file.txt')

    self.assertEqual(
        TripletToComfySchemeURL(comfy_api_url=comfy_api_url,
                                triplet=ComfyUIPathTriplet(
                                    type='input',
                                    subfolder='subfolder',
                                    filename='remote-file.txt')),
        SmartURLJoin(comfy_scheme_url, 'input/subfolder/remote-file.txt'))
    with self.assertRaises(pydantic.ValidationError):
      _ = ComfyUIPathTriplet(type='input',
                             subfolder='/subfolder',
                             filename='remote-file.txt')
    with self.assertRaises(pydantic.ValidationError):
      _ = ComfyUIPathTriplet(type='input',
                             subfolder='/subfolder/',
                             filename='remote-file.txt')
    self.assertEqual(
        TripletToComfySchemeURL(comfy_api_url=comfy_api_url,
                                triplet=ComfyUIPathTriplet(
                                    type='input',
                                    subfolder='subfolder/subsubfolder',
                                    filename='remote-file.txt')),
        SmartURLJoin(comfy_scheme_url,
                     'input/subfolder/subsubfolder/remote-file.txt'))

  async def test_TripletToComfySchemeURL(self):
    for comfy_api_url in [
        'http://comfy_host:23534',
    ]:
      for folder_type in VALID_FOLDER_TYPES:
        with self.subTest(folder_type=folder_type):
          self.assertEqual(
              TripletToComfySchemeURL(comfy_api_url=comfy_api_url,
                                      triplet=ComfyUIPathTriplet(
                                          type=folder_type,
                                          subfolder='',
                                          filename='remote-file.txt')),
              f'comfy+{comfy_api_url}/{folder_type}/remote-file.txt')
          self.assertEqual(
              TripletToComfySchemeURL(comfy_api_url=comfy_api_url,
                                      triplet=ComfyUIPathTriplet(
                                          type=folder_type,
                                          subfolder='subfolder',
                                          filename='remote-file.txt')),
              f'comfy+{comfy_api_url}/{folder_type}/subfolder/remote-file.txt')
          self.assertEqual(
              TripletToComfySchemeURL(comfy_api_url=comfy_api_url,
                                      triplet=ComfyUIPathTriplet(
                                          type=folder_type,
                                          subfolder='subfolder/subsubfolder',
                                          filename='remote-file.txt')),
              f'comfy+{comfy_api_url}/{folder_type}/subfolder/subsubfolder/remote-file.txt'
          )
          self.assertEqual(
              TripletToComfySchemeURL(comfy_api_url=comfy_api_url,
                                      triplet=ComfyUIPathTriplet(
                                          type=folder_type,
                                          subfolder='subfolder/subsubfolder/',
                                          filename='remote-file.txt')),
              f'comfy+{comfy_api_url}/{folder_type}/subfolder/subsubfolder/remote-file.txt'
          )


if __name__ == '__main__':
  unittest.main()
