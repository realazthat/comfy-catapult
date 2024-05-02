#!/bin/bash
# https://gist.github.com/mohanpedala/1e2ff5661761d3abd0385e8223e16425
set -e -x -v -u -o pipefail

SCRIPT_DIR=$(realpath "$(dirname "${BASH_SOURCE[0]}")")
source "${SCRIPT_DIR}/common.sh"

PYTHON_VERSION_PATH=${PYTHON_VERSION_PATH:-}

if [[ -z "${PYTHON_VERSION_PATH}" ]]; then
  echo -e "${RED}PYTHON_VERSION_PATH is not set. Please set it in the calling script${NC}"
  [[ $0 == "${BASH_SOURCE[0]}" ]] && EXIT="exit" || EXIT="return"
  ${EXIT} 1
fi

# Make sure .python-version exists.
if [[ ! -f "${PYTHON_VERSION_PATH}" ]]; then
  [[ $0 == "${BASH_SOURCE[0]}" ]] && EXIT="exit" || EXIT="return"
  echo -e "${RED}.python-version does not exist at ${PYTHON_VERSION_PATH}${NC}"
  ${EXIT} 1
fi

WANTED_PYTHON_VERSION=$(cat "${PYTHON_VERSION_PATH}")

if [[ -z "${WANTED_PYTHON_VERSION}" ]]; then
  echo -e "${RED}WANTED_PYTHON_VERSION is not set, check .python-version${NC}"
  [[ $0 == "${BASH_SOURCE[0]}" ]] && EXIT="exit" || EXIT="return"
  ${EXIT} 1
fi

CURRENT_PYTHON_VERSION_STR=$(python --version||true)

# Check if the current python matches the wanted python
if [[ "${CURRENT_PYTHON_VERSION_STR}" == "Python ${WANTED_PYTHON_VERSION}" ]]; then
  echo -e "${GREEN}Python version matches${NC}"
  [[ $0 == "${BASH_SOURCE[0]}" ]] && EXIT="exit" || EXIT="return"
  ${EXIT} 0
fi

export PYENV_ROOT="${HOME}/.pyenv"
export PATH="${PYENV_ROOT}/bin:${PATH}"

CURRENT_PWD="${PWD}"

# if PYENV_ROOT doesn't exist, install pyenv
if [[ ! -d "${PYENV_ROOT}" ]]; then
  echo -e "${YELLOW}pyenv is not installed${NC}"
  cd ~
  curl -L https://github.com/pyenv/pyenv/archive/21c2a3dd6944bf2f0cb4e3bb8f217e9138aaaf55.zip -o pyenv-21c2a3dd.zip
  unzip pyenv-21c2a3dd.zip -d ~/unzipped
  mv ~/unzipped/pyenv-21c2a3dd6944bf2f0cb4e3bb8f217e9138aaaf55/ ~/.pyenv
  ls
  cd "${PYENV_ROOT}"
  ls
  cd "${PYENV_ROOT}" && src/configure && make -C src
  cd "${CURRENT_PWD}"
fi


eval "$(pyenv init --path||true)"
# eval "$(pyenv virtualenv-init -)"


echo -e "${YELLOW}Installing python version from .python-version${NC}"
echo -e "${YELLOW}This may take a while${NC}"
echo -e "${YELLOW}WANTED_PYTHON_VERSION: ${WANTED_PYTHON_VERSION}${NC}"
pyenv install --skip-existing "${WANTED_PYTHON_VERSION}"

ACTUAL_PYTHON_VERSION=$(python --version)
echo -e "${YELLOW}ACTUAL_PYTHON_VERSION: ${ACTUAL_PYTHON_VERSION}${NC}"
WHICH_PYTHON=$(command -v python)
echo -e "${YELLOW}WHICH_PYTHON: ${WHICH_PYTHON}${NC}"
ls ~/.pyenv/versions/

echo -e "${GREEN}pyenv is installed and the requested .python-version is installed${NC}"
