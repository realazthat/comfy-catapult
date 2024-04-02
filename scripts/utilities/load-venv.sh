#!/bin/bash
# https://gist.github.com/mohanpedala/1e2ff5661761d3abd0385e8223e16425
set -e -x -v -u -o pipefail

SCRIPT_DIR=$(realpath "$(dirname "${BASH_SOURCE[0]}")")
source "${SCRIPT_DIR}/common.sh"

source "${PROJ_PATH}/scripts/utilities/ensure-pyenv.sh"

VENV_PATH=${VENV_PATH:-""}

if [[ -z "${VENV_PATH}" ]]; then
  echo -e "${RED}VENV_PATH is not set${NC}"
  [[ $0 == "${BASH_SOURCE[0]}" ]] && EXIT="exit" || EXIT="return"
  ${EXIT} 1
fi

echo -e "${GREEN}Found ${VENV_PATH}/bin/activate${NC}"
# trunk-ignore(shellcheck/SC1091)
source "${VENV_PATH}/bin/activate"

source "${PROJ_PATH}/scripts/utilities/ensure-py-version.sh"

echo -e "${GREEN}Successfully loaded ${VENV_PATH}/bin/activate${NC}"
