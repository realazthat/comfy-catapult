#!/bin/bash
# https://gist.github.com/mohanpedala/1e2ff5661761d3abd0385e8223e16425
set -e -x -v -u -o pipefail

################################################################################
SCRIPT_DIR=$(realpath "$(dirname "${BASH_SOURCE[0]}")")
source "${SCRIPT_DIR}/utilities/common.sh"

VENV_PATH=${PWD}/.cache/scripts/.venv source "${PROJ_PATH}/scripts/utilities/ensure-venv.sh"
TOML=${PROJ_PATH}/pyproject.toml EXTRA=dev \
  DEV_VENV_PATH="${PWD}/.cache/scripts/.venv" \
  TARGET_VENV_PATH="${PWD}/.cache/scripts/.venv" \
  bash "${PROJ_PATH}/scripts/utilities/ensure-reqs.sh"
################################################################################
python -m snipinator.cli \
  -t "${PROJ_PATH}/README.md.jinja2" \
  --rm \
  --force \
  --create \
  -o "${PROJ_PATH}/README.md" \
  --chmod-ro
################################################################################
LAST_VERSION=$(tomlq -r -e '.["tool"]["comfy_catapult-project-metadata"]["last_stable_release"]' pyproject.toml)
python -m mdremotifier.cli \
  -i "${PROJ_PATH}/README.md" \
  --url-prefix "https://github.com/realazthat/comfy-catapult/blob/v${LAST_VERSION}/" \
  --img-url-prefix "https://raw.githubusercontent.com/realazthat/comfy-catapult/v${LAST_VERSION}/" \
  -o "${PROJ_PATH}/.github/README.remotified.md"
################################################################################
