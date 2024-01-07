# -*- coding: utf-8 -*-


# SPDX-License-Identifier: MIT
#
# The Catapult require contributions made to this file be licensed under the MIT
# license or a compatible open source license. See LICENSE.md for the license
# text.

import argparse
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

parser = argparse.ArgumentParser(description='Generate README.md')

parser.add_argument('template', type=Path, help='Input file')

args = parser.parse_args()


env = Environment(
    loader=FileSystemLoader(searchpath='.'),
    autoescape=select_autoescape()
)

template = env.get_template(str(args.template))

variables = {}

readme_content = template.render(variables)

print(readme_content)
