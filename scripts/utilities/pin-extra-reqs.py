# -*- coding: utf-8 -*-
import argparse
from pathlib import Path
from typing import List, Tuple

# tomlkit is used, so that everything is preserved, e.g comments etc.
import tomlkit
import tomlkit.container
import tomlkit.items
from tomlkit.toml_document import TOMLDocument

_VALID_EXTRA_NAMES = ['dev', 'prod']

_DESCRIPTION = f"""
Pin the {{{",".join(_VALID_EXTRA_NAMES)}}} requirements in pyproject.toml.

The purpose of this program is to take the output of
`pip-compile --extra EXTRA pyproject.toml` and reinsert the exactly
to-be-installed version numbers back into the updated pyproject.toml.

This ensures that there is a valid, and consistent version of dependencies that
are known to work.
"""
parser = argparse.ArgumentParser(description=_DESCRIPTION)
parser.add_argument('--toml',
                    type=Path,
                    required=True,
                    help='Path to the pyproject.toml file')
parser.add_argument('--extra',
                    choices=_VALID_EXTRA_NAMES,
                    required=True,
                    help='Which extra requirements to pin (dev/prod)')
parser.add_argument(
    '--reqs',
    type=Path,
    required=True,
    help='Path to the generated requirements.txt file (from pip-compile)')
args = parser.parse_args()

pyproject_path: Path = args.toml
requirements_path: Path = args.reqs
extra_name: str = args.extra

pyproject_data: TOMLDocument = tomlkit.loads(pyproject_path.read_text())
lines = requirements_path.read_text().splitlines()


def _StripContinuation(line) -> Tuple[bool, str]:
  line = line.strip()
  if line.endswith('\\'):
    return (True, line[:-1].strip())
  return (False, line)


existing_dependencies: List[str] = []
is_continuation = False
for i in range(len(lines)):
  line = lines[i]
  append_to_last = is_continuation
  is_continuation, stripped_line = _StripContinuation(line)
  if not stripped_line:
    continue
  if stripped_line.startswith('#'):
    continue
  if stripped_line.startswith('--'):
    continue
  if append_to_last:
    existing_dependencies[-1] += stripped_line
  else:
    existing_dependencies.append(stripped_line)

if 'project' not in pyproject_data:
  raise ValueError('Invalid pyproject.toml file, missing "project" section.')
project_item = pyproject_data['project']
if not isinstance(project_item, tomlkit.items.Table):
  raise ValueError(
      f'Invalid pyproject.toml file, expected "project" to be a table. Got {type(project_item)}.'
  )

if 'optional-dependencies' not in project_item:
  raise ValueError(
      'Invalid pyproject.toml file, expected "project" to have an entry for "optional-dependencies".'
  )
opt_deps = project_item['optional-dependencies']
if not isinstance(opt_deps, tomlkit.items.Table):
  raise ValueError(
      f'Invalid pyproject.toml file, expected "project.optional-dependencies" to be a table. Got {type(opt_deps)}.'
  )

if extra_name not in opt_deps:
  raise ValueError(
      f'Invalid pyproject.toml file, expected "project.optional-dependencies" to contain {extra_name}.'
  )
toml_extra_dependencies = opt_deps[extra_name]
if not isinstance(toml_extra_dependencies, tomlkit.items.Array):
  raise ValueError(
      f'Invalid pyproject.toml file, expected "project.optional-dependencies.{extra_name}" to be an array. Got {type(toml_extra_dependencies)}.'
  )
if sorted(list(toml_extra_dependencies)) == sorted(existing_dependencies):
  print('No changes detected')
  exit(0)

toml_extra_dependencies.clear()
for dep in existing_dependencies:
  toml_extra_dependencies.append(dep)
opt_deps[extra_name] = toml_extra_dependencies.multiline(True)

output = tomlkit.dumps(pyproject_data)
if output == pyproject_path.read_text():
  print('No changes detected')
  exit(0)

# Write the updated pyproject.toml back to disk
pyproject_path.write_text(tomlkit.dumps(pyproject_data))
