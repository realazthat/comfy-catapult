#!/bin/bash
# https://gist.github.com/mohanpedala/1e2ff5661761d3abd0385e8223e16425
set -e -x -v -u -o pipefail

SCRIPT_DIR=$(realpath "$(dirname "${BASH_SOURCE[0]}")")
source "${SCRIPT_DIR}/common.sh"

VENV_PATH="${PWD}/.cache/scripts/.venv" source "${PROJ_PATH}/scripts/utilities/ensure-venv.sh"
TOML=${PROJ_PATH}/pyproject.toml EXTRA=dev \
  DEV_VENV_PATH="${PWD}/.cache/scripts/.venv" \
  TARGET_VENV_PATH="${PWD}/.cache/scripts/.venv" \
  bash "${PROJ_PATH}/scripts/utilities/ensure-reqs.sh"



EXTRA=${EXTRA:-}

if [[ "${EXTRA}" == "dev" ]]; then
  :
elif [[ "${EXTRA}" == "prod" ]]; then
  :
else
  echo -e "${RED}EXTRA must be set to 'dev' or 'prod'${NC}"
  [[ $(realpath "$0"||true) == $(realpath "${BASH_SOURCE[0]}"||true) ]] && EXIT="exit" || EXIT="return"
  ${EXIT} 1
fi

################################################################################
TOML_FILE=${PROJ_PATH}/pyproject.toml
PINNED_REQ_FILE="${PWD}/.cache/scripts/${EXTRA}-requirements.pinned.txt"
PINNED_REQ_TOUCH_FILE="${PWD}/.cache/scripts/${EXTRA}-requirements.pinned.touch"
TOML_UPDATE_TOUCH_FILE="${PWD}/.cache/scripts/${EXTRA}-pyproject.toml.pinned.touch"
################################################################################
# Extract the requirements from the pyproject.toml file into a requirements
# file.
#
# Check if we already did this.
export FILE="${TOML_FILE}"
export TOUCH_FILE="${PINNED_REQ_TOUCH_FILE}"
if bash "${PROJ_PATH}/scripts/utilities/is_not_dirty.sh"; then
  echo -e "${GREEN}Requirements ${PINNED_REQ_FILE} are up to date${NC}"
  [[ $(realpath "$0"||true) == $(realpath "${BASH_SOURCE[0]}"||true) ]] && EXIT="exit" || EXIT="return"
else
  echo -e "${BLUE}Requirements ${PINNED_REQ_FILE} need updating${NC}"
  echo -e "${BLUE}Generating ${PINNED_REQ_FILE}${NC}"

  PINNED_REQ_DIR=$(dirname "${PINNED_REQ_FILE}")
  mkdir -p "${PINNED_REQ_DIR}"
  python -m piptools compile --generate-hashes \
    --extra "${EXTRA}" \
    "${TOML_FILE}" \
    -o "${PINNED_REQ_FILE}"
  echo -e "${GREEN}Generated ${PINNED_REQ_FILE}${NC}"

  export FILE="${TOML_FILE}"
  export TOUCH_FILE="${PINNED_REQ_TOUCH_FILE}"
  bash "${PROJ_PATH}/scripts/utilities/mark_dirty.sh"
fi
################################################################################
# Pin extra requirements in pyproject.toml file.

export FILE="${TOML_FILE}"
export TOUCH_FILE="${TOML_UPDATE_TOUCH_FILE}"
if bash "${PROJ_PATH}/scripts/utilities/is_not_dirty.sh"; then
  echo -e "${GREEN}pyproject.toml is up to date${NC}"
else
  echo -e "${BLUE}Altering pyproject.toml${NC}"
  python "${PROJ_PATH}/scripts/utilities/pin-extra-reqs.py" \
    --reqs "${PINNED_REQ_FILE}" \
    --extra "${EXTRA}" \
    --toml "${TOML_FILE}"
  ################################################################################
  # Format the pyproject.toml file
  if toml-sort "${TOML_FILE}" --check; then
    echo -e "${GREEN}pyproject.toml needs no formatting${NC}"
  else
    echo -e "${BLUE}pyproject.toml needs formatting${NC}"
    toml-sort --in-place "${TOML_FILE}"
    echo -e "${GREEN}pyproject.toml formatted${NC}"
  fi
  if toml-sort "${TOML_FILE}" --check; then
    echo -e "${GREEN}pyproject.toml is formatted${NC}"
  else
    echo -e "${RED}pyproject.toml is not formatted${NC}"
    [[ $(realpath "$0"||true) == $(realpath "${BASH_SOURCE[0]}"||true) ]] && EXIT="exit" || EXIT="return"
    ${EXIT} 1
  fi
  ################################################################################
  export FILE="${TOML_FILE}"
  export TOUCH_FILE="${TOML_UPDATE_TOUCH_FILE}"
  bash "${PROJ_PATH}/scripts/utilities/mark_dirty.sh"
  echo -e "${GREEN}Pinned ${EXTRA} requirements${NC}"
fi
