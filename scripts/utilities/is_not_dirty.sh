#!/bin/bash
# https://gist.github.com/mohanpedala/1e2ff5661761d3abd0385e8223e16425
set -e -x -v -u -o pipefail

SCRIPT_DIR=$(realpath "$(dirname "${BASH_SOURCE[0]}")")
source "${SCRIPT_DIR}/common.sh"

DIRTY_METHOD=${DIRTY_METHOD:-"xxhash"}

if [[ -z "${TOUCH_FILE:-}" ]]; then
  echo -e "${RED}TOUCH_FILE is not set${NC}"
  [[ $0 == "${BASH_SOURCE[0]}" ]] && EXIT="exit" || EXIT="return"
  ${EXIT} 1
fi

if [[ -z "${FILE:-}" ]]; then
  echo -e "${RED}FILE is not set${NC}"
  [[ $0 == "${BASH_SOURCE[0]}" ]] && EXIT="exit" || EXIT="return"
  ${EXIT} 1
fi

if [[ "${DIRTY_METHOD}" == "stat" ]]; then
  TOUCH_TIME=$(stat -c '%y' "${TOUCH_FILE}")
  FILE_TIME=$(stat -c '%y' "${FILE}")
  echo "TOUCH_TIME: ${TOUCH_TIME}"
  echo "FILE_TIME:       ${FILE_TIME}"
  if [[ ! -f "${TOUCH_FILE}" ]]; then
    [[ $0 == "${BASH_SOURCE[0]}" ]] && EXIT="exit" || EXIT="return"
    ${EXIT} 1
  fi
  if [[ "${TOUCH_FILE}" -nt "${FILE}" ]]; then
    [[ $0 == "${BASH_SOURCE[0]}" ]] && EXIT="exit" || EXIT="return"
    ${EXIT} 0
  else
    [[ $0 == "${BASH_SOURCE[0]}" ]] && EXIT="exit" || EXIT="return"
    ${EXIT} 1
  fi
elif [[ "${DIRTY_METHOD}" == "xxhash" ]]; then
  if [[ ! -f "${TOUCH_FILE}" ]]; then
    [[ $0 == "${BASH_SOURCE[0]}" ]] && EXIT="exit" || EXIT="return"
    ${EXIT} 1
  fi
  FILE_XXHASH=$(xxh128sum "${FILE}" | awk '{print $1}')
  TOUCH_XXHASH=$(awk '{print $1}' < "${TOUCH_FILE}")
  if [[ "${FILE_XXHASH}" != "${TOUCH_XXHASH}" ]]; then
    [[ $0 == "${BASH_SOURCE[0]}" ]] && EXIT="exit" || EXIT="return"
    ${EXIT} 1
  else
    [[ $0 == "${BASH_SOURCE[0]}" ]] && EXIT="exit" || EXIT="return"
    ${EXIT} 0
  fi
else
  echo -e "${RED}DIRTY_METHOD should be either stat or xxhash${NC}"
  [[ $0 == "${BASH_SOURCE[0]}" ]] && EXIT="exit" || EXIT="return"
  ${EXIT} 1
fi
