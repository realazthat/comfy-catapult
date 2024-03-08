#!/bin/bash
# https://gist.github.com/mohanpedala/1e2ff5661761d3abd0385e8223e16425
set -e -x -v -u -o pipefail

SCRIPT_DIR=$(realpath "$(dirname "${BASH_SOURCE[0]}")")
source "${SCRIPT_DIR}/utilities/common.sh"

VENV_PATH=.cache/scripts/.venv source "${PROJ_PATH}/scripts/utilities/ensure-venv.sh"

REQS="${PROJ_PATH}/scripts/requirements-dev.txt" source "${PROJ_PATH}/scripts/utilities/ensure-reqs.sh"

# Must have mdformat-gfm installed, otherwise checkboxes get messed up
mdformat README.md.jinja2

yapf -r ./comfy_catapult ./examples -i
yapf ./setup.py -i
autoflake --remove-all-unused-imports --in-place --recursive ./comfy_catapult ./examples
isort ./comfy_catapult ./examples

# vulture ./comfy_catapult ./examples
