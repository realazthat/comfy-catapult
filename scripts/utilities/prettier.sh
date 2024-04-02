#!/bin/bash
# https://gist.github.com/mohanpedala/1e2ff5661761d3abd0385e8223e16425
set -e -x -v -u -o pipefail

# All arguments to this script will be passed to prettier.
#
# NOTE: Beware, that all paths must be absolute, otherwise the script will fail.

SCRIPT_DIR=$(realpath "$(dirname "${BASH_SOURCE[0]}")")
source "${SCRIPT_DIR}/common.sh"

# CURRENT_PWD=${PWD}
PRETTIER_BUILD_PATH=${NODE_APP_PATH:-${PWD}/.cache/scripts/prettier-build}

export NVM_DIR=${NVM_DIR:-"${HOME}/.nvm"}


mkdir -p "${PRETTIER_BUILD_PATH}"
cd "${PRETTIER_BUILD_PATH}"

if npx --no-install prettier --version &>/dev/null; then
  echo -e "${BLUE}Prettier is installed${NC}"
else
  echo -e "${BLUE}Prettier is not installed${NC}"

  # sourcing nvm.sh when .nvmrc is present can return an error with no message
  # (https://github.com/nvm-sh/nvm/issues/1985).
  rm .nvmrc || true
  { set +x +v; } 2>/dev/null; [[ -s "${NVM_DIR}/nvm.sh" ]] && \. "${NVM_DIR}/nvm.sh"; set -x -v
  echo v20.11.1 > .nvmrc
  { set +x; } 2>/dev/null; nvm install; set -x
  { set +x; } 2>/dev/null; nvm use; set -x
  { set +x; } 2>/dev/null; npm init -y; set -x
  { set +x; } 2>/dev/null; npm install --save prettier@3.2.4; set -x
fi

npx prettier "$@"
