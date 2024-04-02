#!/bin/bash
# https://gist.github.com/mohanpedala/1e2ff5661761d3abd0385e8223e16425
set -e -x -v -u -o pipefail

SCRIPT_DIR=$(realpath "$(dirname "${BASH_SOURCE[0]}")")
source "${SCRIPT_DIR}/common.sh"

DIRTY_METHOD=${DIRTY_METHOD:-"xxhash"}
FILE=${FILE-}
TOUCH_FILE=${TOUCH_FILE-}

if [[ -z "${FILE:-}" ]]; then
  echo -e "${RED}FILE is not set${NC}"
  [[ $0 == "${BASH_SOURCE[0]}" ]] && EXIT="exit" || EXIT="return"
  ${EXIT} 1
fi

if [[ -z "${TOUCH_FILE:-}" ]]; then
  echo -e "${RED}TOUCH_FILE is not set${NC}"
  [[ $0 == "${BASH_SOURCE[0]}" ]] && EXIT="exit" || EXIT="return"
  ${EXIT} 1
fi
################################################################################
# Mark it.

if [[ "${DIRTY_METHOD}" == "stat" ]]; then
  touch "${TOUCH_FILE}"
elif [[ "${DIRTY_METHOD}" == "xxhash" ]]; then
  xxh128sum "${FILE}" > "${TOUCH_FILE}"
else
  echo -e "${RED}DIRTY_METHOD should be either stat or xxhash${NC}"
  [[ $0 == "${BASH_SOURCE[0]}" ]] && EXIT="exit" || EXIT="return"
  ${EXIT} 1
fi
################################################################################
# Check if it worked
export FILE="${FILE}"
export TOUCH_FILE="${TOUCH_FILE}"
if bash "${PROJ_PATH}/scripts/utilities/is_not_dirty.sh"; then
  :
else
  echo -e "${RED}${FILE} is dirty, mark_dirty failed${NC}"
  [[ $(realpath "$0"||true) == $(realpath "${BASH_SOURCE[0]}"||true) ]] && EXIT="exit" || EXIT="return"
  ${EXIT} 1
fi
################################################################################
