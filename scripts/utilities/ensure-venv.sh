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

# Check if $VENV_PATH/bin/activate exists
if [[ -f "${VENV_PATH}/bin/activate" ]]; then
  if source "${PROJ_PATH}/scripts/utilities/load-venv.sh"; then
    [[ $0 == "${BASH_SOURCE[0]}" ]] && EXIT="exit" || EXIT="return"
    ${EXIT} 0
  else
    echo -e "${RED}Failed to load ${VENV_PATH}/bin/activate${NC}"
    [[ $0 == "${BASH_SOURCE[0]}" ]] && EXIT="exit" || EXIT="return"
    ${EXIT} 1
  fi
fi

pip install virtualenv
python -m virtualenv "${VENV_PATH}"
echo -e "${GREEN}Created ${VENV_PATH}${NC}"

source "${PROJ_PATH}/scripts/utilities/load-venv.sh"
