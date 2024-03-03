# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT
#
# The Comfy Catapult project requires contributions made to this file be licensed
# under the MIT license or a compatible open source license. See LICENSE.md for
# the license text.

from setuptools import setup, find_packages

with open('README.md') as f:
  long_description = f.read()
with open('requirements.txt') as f:
  requirements = f.read().splitlines()
  requirements = [r.strip() for r in requirements]
  requirements = [r for r in requirements if len(r) > 0]
  requirements = [r for r in requirements if not r.startswith('#')]

setup(
    name='comfy_catapult',
    version='2.0.0-alpha',
    packages=find_packages(exclude=['examples']),
    description='Programmatically schedule ComfyUI workflows',
    long_description=long_description,
    long_description_content_type='text/markdown',
    author='AYF',
    author_email='realazthat@gmail.com',
    url='https://github.com/realazthat/comfy-catapult',
    install_requires=requirements,
    classifiers=[
        # Choose your license and programming language/version here. For example:
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.10',
    ],
)
