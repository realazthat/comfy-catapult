# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT
#
# The Catapult require contributions made to this file be licensed under the MIT
# license or a compatible open source license. See LICENSE.md for the license
# text.

import unittest
from unittest import IsolatedAsyncioTestCase

import aiofiles
import yaml

from comfy_catapult.comfy_schema import APIObjectInfo
from comfy_catapult.comfy_utils import TryParseAsModel


class TestComfySchema(IsolatedAsyncioTestCase):

  async def test_comfy_schema(self):
    async with aiofiles.open('test_data/object_info.yml') as f:
      content = yaml.load(await f.read(), Loader=yaml.FullLoader)
    await TryParseAsModel(content=content,
                          model_type=APIObjectInfo,
                          strict='yes')


if __name__ == '__main__':
  unittest.main()
