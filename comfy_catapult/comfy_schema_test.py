# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT
#
# The Comfy Catapult project requires contributions made to this file be licensed
# under the MIT license or a compatible open source license. See LICENSE.md for
# the license text.

import unittest
from typing import List, Tuple, Type
from unittest import IsolatedAsyncioTestCase

import aiofiles
import pydantic
import yaml

from .comfy_schema import VALID_FOLDER_TYPES, APIObjectInfo, ComfyUIPathTriplet
from .comfy_utils import TryParseAsModel

INVALID_SUBFOLDER_EDGES: List[Tuple[str, Type[Exception]]] = [
    ('/', pydantic.ValidationError),
    ('/subfolder', pydantic.ValidationError),
    ('/subfolder/', pydantic.ValidationError),
    ('/subfolder/subsubfolder', pydantic.ValidationError),
    ('/subfolder/subsubfolder/', pydantic.ValidationError),
]

VALID_SUBFOLDER_EDGES: List[Tuple[str, str]] = [
    ('', ''),
    ('subfolder', 'subfolder'),
    ('./subfolder', './subfolder'),
    ('subfolder/', 'subfolder/'),
    ('subfolder/subsubfolder/', 'subfolder/subsubfolder/'),
    ('subfolder/subsubfolder', 'subfolder/subsubfolder'),
    ('subfolder/./subsubfolder', 'subfolder/./subsubfolder'),
    ('subfolder/../subsubfolder', 'subfolder/../subsubfolder'),
]


class TestComfySchema(IsolatedAsyncioTestCase):

  async def test_comfy_schema(self):
    async with aiofiles.open('test_data/object_info.yml') as f:
      content = yaml.safe_load(await f.read())
    await TryParseAsModel(content=content,
                          model_type=APIObjectInfo,
                          errors_dump_directory=None,
                          strict='yes')

  def test_ComfyUIPathTriplet_Scheme(self):
    # Simple cases.
    _ = ComfyUIPathTriplet(type='input',
                           subfolder='subfolder',
                           filename='filename.txt')
    # These should be OK
    _ = ComfyUIPathTriplet(type='input',
                           subfolder='subfolder',
                           filename='filename.txt')
    _ = ComfyUIPathTriplet(type='input',
                           subfolder='./subfolder',
                           filename='filename.txt')
    _ = ComfyUIPathTriplet(type='input',
                           subfolder='./subfolder/',
                           filename='filename.txt')
    _ = ComfyUIPathTriplet(type='input',
                           subfolder='./subfolder/subsubfolder',
                           filename='filename.txt')

  def test_ComfyUIPathTriplet_Folder(self):
    # Simple cases.
    _ = ComfyUIPathTriplet(type='input',
                           subfolder='subfolder',
                           filename='filename.txt')

    with self.assertRaises(pydantic.ValidationError) as cm:
      _ = ComfyUIPathTriplet(
          type='not-valid-folder-type',  # type: ignore
          subfolder='subfolder',
          filename='filename.txt')
    self.assertIn("Input should be 'input', 'output' or 'temp'",
                  str(cm.exception).strip())

    with self.assertRaises(pydantic.ValidationError) as cm:
      _ = ComfyUIPathTriplet(type='input',
                             subfolder='subfolder',
                             filename='/filename.txt')
    self.assertIn(
        "Value error, filename '/filename.txt' must not contain a slash",
        str(cm.exception).strip())

    with self.assertRaises(pydantic.ValidationError) as cm:
      _ = ComfyUIPathTriplet(type='input', subfolder='subfolder', filename='')
    self.assertIn("Value error, filename '' must not be empty",
                  str(cm.exception).strip())

    with self.assertRaises(pydantic.ValidationError) as cm:
      _ = ComfyUIPathTriplet(type='input',
                             subfolder='/subfolder',
                             filename='filename.txt')
    self.assertIn(
        "Value error, subfolder '/subfolder' must not start with a slash",
        str(cm.exception).strip())

  def test_ComfyUIPathTripletEdges(self):

    for folder_type in VALID_FOLDER_TYPES:
      for subfolder, _ in VALID_SUBFOLDER_EDGES:
        with self.subTest(folder_type=folder_type, subfolder=subfolder):
          triplet = ComfyUIPathTriplet(type=folder_type,
                                       subfolder=subfolder,
                                       filename='remote-file.txt')
          self.assertEqual(triplet.subfolder, subfolder)
      for subfolder, expected_exception in INVALID_SUBFOLDER_EDGES:
        with self.subTest(folder_type=folder_type, subfolder=subfolder):
          with self.assertRaises(expected_exception):
            triplet = ComfyUIPathTriplet(type=folder_type,
                                         subfolder=subfolder,
                                         filename='remote-file.txt')


if __name__ == '__main__':
  unittest.main()
