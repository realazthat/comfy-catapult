#!/bin/bash
# https://gist.github.com/mohanpedala/1e2ff5661761d3abd0385e8223e16425
set -e -x -v -u -o pipefail

SCRIPT_DIR=$(realpath "$(dirname "${BASH_SOURCE[0]}")")
source "${SCRIPT_DIR}/common.sh"

PYTHON_VERSION_PATH=${PYTHON_VERSION_PATH:-"${PWD}/.python-version"}
EXPECTED_PYTHON_VERSION=$(cat "${PYTHON_VERSION_PATH}")
# Get ONLY the version number, not the whole string
PYTHON_VERSION=$(python -c "import sys; print(sys.version.split()[0])")

if command -v pyenv 1>/dev/null 2>&1; then
  # Sometimes .python-version name does not match python --version, such as
  # `3.13-dev` vs `3.13.0a5+`, so we check for the name via pyenv directly.

  # This will match the .python-version file contents if it was loaded from
  # there.
  PYENV_VERSION_NAME=$(pyenv version-name||true)
  PYENV_VERSION_FILE=$(pyenv version-file||true)
  PYENV_PYTHON_PATH=$(pyenv which python||true)
  PYENV_PYTHON_VERSION=$("${PYENV_PYTHON_PATH}" -c "import sys; print(sys.version.split()[0])"||true)

  # If PYENV_VERSION_FILE is $PWD/.python-version, then we are using pyenv
  if [[ "${PYENV_VERSION_FILE}" == "${PYTHON_VERSION_PATH}" ]]; then
    if [[ "${PYENV_VERSION_NAME}" == "${EXPECTED_PYTHON_VERSION}" ]]; then
      if [[ "${PYENV_PYTHON_VERSION}" == "${PYTHON_VERSION}" ]]; then
        echo -e "${GREEN}Python version matches${NC}"
        [[ $0 == "${BASH_SOURCE[0]}" ]] && EXIT="exit" || EXIT="return"
        ${EXIT} 0
      fi
    fi
  fi
fi

if [[ "${PYTHON_VERSION}" != "${EXPECTED_PYTHON_VERSION}" ]]; then
  echo -e "${RED}Expected python version ${EXPECTED_PYTHON_VERSION}, got ${PYTHON_VERSION}${NC}"
  [[ $0 == "${BASH_SOURCE[0]}" ]] && EXIT="exit" || EXIT="return"
  ${EXIT} 1
fi
