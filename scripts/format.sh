#!/bin/bash
# https://gist.github.com/mohanpedala/1e2ff5661761d3abd0385e8223e16425
set -e -x -v -u -o pipefail

SCRIPT_DIR=$(realpath "$(dirname "${BASH_SOURCE[0]}")")
source "${SCRIPT_DIR}/utilities/common.sh"

VENV_PATH=${PWD}/.cache/scripts/.venv source "${PROJ_PATH}/scripts/utilities/ensure-venv.sh"
TOML=${PROJ_PATH}/pyproject.toml EXTRA=dev \
  DEV_VENV_PATH="${PWD}/.cache/scripts/.venv" \
  TARGET_VENV_PATH="${PWD}/.cache/scripts/.venv" \
  bash "${PROJ_PATH}/scripts/utilities/ensure-reqs.sh"

bash scripts/utilities/prettier.sh --parser markdown "${PWD}/README.md.jinja2" --write

yapf -r ./comfy_catapult ./examples ./scripts -i
autoflake --remove-all-unused-imports --in-place --recursive ./comfy_catapult ./examples
isort ./comfy_catapult ./examples ./scripts 

# vulture ./comfy_catapult ./examples
