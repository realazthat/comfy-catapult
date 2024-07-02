# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT
#
# The Comfy Catapult project requires contributions made to this file be licensed
# under the MIT license or a compatible open source license. See LICENSE.md for
# the license text.

import unittest

from .url_utils import JoinToBaseURL


class TestUrlUtils(unittest.TestCase):

  def test_JoinToBaseURL(self):
    self.assertEqual(JoinToBaseURL('http://example.com', 'path'),
                     'http://example.com/path')
    self.assertEqual(JoinToBaseURL('http://example.com/', 'path'),
                     'http://example.com/path')
    self.assertEqual(JoinToBaseURL('http://example.com', '/path'),
                     'http://example.com/path')
    self.assertEqual(JoinToBaseURL('http://example.com/', '/path'),
                     'http://example.com/path')

    self.assertEqual(JoinToBaseURL('http://example.com/path', 'to'),
                     'http://example.com/path/to')
    self.assertEqual(JoinToBaseURL('http://example.com/path/', 'to'),
                     'http://example.com/path/to')
    self.assertEqual(JoinToBaseURL('http://example.com/path', '/to'),
                     'http://example.com/path/to')
    self.assertEqual(JoinToBaseURL('http://example.com/path/', '/to'),
                     'http://example.com/path/to')


if __name__ == '__main__':
  unittest.main(buffer=True)
