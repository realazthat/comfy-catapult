#!/bin/bash
# https://gist.github.com/mohanpedala/1e2ff5661761d3abd0385e8223e16425
set -e -x -v -u -o pipefail

SCRIPT_DIR=$(realpath "$(dirname "${BASH_SOURCE[0]}")")
source "${SCRIPT_DIR}/common.sh"

TOML=${TOML:-""}
EXTRA=${EXTRA:-""}
DEV_VENV_PATH=${DEV_VENV_PATH:-}
TARGET_VENV_PATH=${TARGET_VENV_PATH:-}

if [[ $(realpath "$0"||true) == $(realpath "${BASH_SOURCE[0]}"||true) ]]; then
  :
else
  echo -e "${RED}This script should NOT be sourced, execute it like a normal script.${NC}"
  return 1
fi
if [[ -z "${TOML}" ]]; then
  echo -e "${RED}TOML is not set${NC}"
  [[ $(realpath "$0"||true) == $(realpath "${BASH_SOURCE[0]}"||true) ]] && EXIT="exit" || EXIT="return"
  ${EXIT} 1
fi

if [[ "${EXTRA}" == "dev" ]]; then
  :
elif [[ "${EXTRA}" == "prod" ]]; then
  :
else
  echo -e "${RED}EXTRA should be either dev or prod${NC}"
  [[ $(realpath "$0"||true) == $(realpath "${BASH_SOURCE[0]}"||true) ]] && EXIT="exit" || EXIT="return"
  ${EXIT} 1
fi
if [[ -z "${DEV_VENV_PATH}" ]]; then
  echo -e "${RED}DEV_VENV_PATH is not set${NC}"
  [[ $(realpath "$0"||true) == $(realpath "${BASH_SOURCE[0]}"||true) ]] && EXIT="exit" || EXIT="return"
  ${EXIT} 1
fi
if [[ -z "${TARGET_VENV_PATH}" ]]; then
  echo -e "${RED}TARGET_VENV_PATH is not set${NC}"
  [[ $(realpath "$0"||true) == $(realpath "${BASH_SOURCE[0]}"||true) ]] && EXIT="exit" || EXIT="return"
  ${EXIT} 1
fi
################################################################################
# Get the target python executable, where we want to install all the
# requirements to.
VENV_PATH=${TARGET_VENV_PATH} source "${PROJ_PATH}/scripts/utilities/ensure-venv.sh"
PYTHON_EXECUTABLE=$(command -v python)
################################################################################
# Activate the dev venv to install pip-tools to etc.
VENV_PATH=${DEV_VENV_PATH} source "${PROJ_PATH}/scripts/utilities/ensure-venv.sh"
################################################################################

SYNC_TOUCH_FILE="${PWD}/.cache/scripts/${EXTRA}-requirements.touch"
OUTPUT_REQUIREMENTS_FILE="${PWD}/.cache/scripts/${EXTRA}-requirements.txt"

export FILE=${TOML}
export TOUCH_FILE=${SYNC_TOUCH_FILE}
if bash "${PROJ_PATH}/scripts/utilities/is_not_dirty.sh"; then
  echo -e "${GREEN}Syncing is not needed${NC}"
  [[ $(realpath "$0"||true) == $(realpath "${BASH_SOURCE[0]}"||true) ]] && EXIT="exit" || EXIT="return"
  ${EXIT} 0
fi
echo -e "${BLUE}Syncing requirements${NC}"

python -m pip install pip-tools

mkdir -p "$(dirname "${OUTPUT_REQUIREMENTS_FILE}")"
python -m piptools compile \
    --extra "${EXTRA}" \
    -o "${OUTPUT_REQUIREMENTS_FILE}" \
    "${TOML}"

python -m piptools sync "${OUTPUT_REQUIREMENTS_FILE}" \
  --python-executable "${PYTHON_EXECUTABLE}"

export FILE=${TOML}
export TOUCH_FILE=${SYNC_TOUCH_FILE}
bash "${PROJ_PATH}/scripts/utilities/mark_dirty.sh"

export FILE=${TOML}
export TOUCH_FILE=${SYNC_TOUCH_FILE}
if bash "${PROJ_PATH}/scripts/utilities/is_not_dirty.sh"; then
  :
else
  echo -e "${RED}Syncing failed${NC}"
  [[ $(realpath "$0"||true) == $(realpath "${BASH_SOURCE[0]}"||true) ]] && EXIT="exit" || EXIT="return"
  ${EXIT} 1
fi

echo -e "${GREEN}Synced requirements for ${EXTRA}, using ${OUTPUT_REQUIREMENTS_FILE}${NC}"
