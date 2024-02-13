#!/bin/bash

# https://gist.github.com/mohanpedala/1e2ff5661761d3abd0385e8223e16425
set -e -x -v -u -o pipefail

SCRIPT_DIR=$(realpath "$(dirname "${BASH_SOURCE[0]}")")
source "${SCRIPT_DIR}/utilities/common.sh"

ENV_VARS_FILE=${ENV_VARS_FILE:-""}
PROJECT_RO_PATH=/ci-project-ro/
PROJECT_CLONE_PATH=/ci-project-export/
IMAGE_PREFIX=${IMAGE_PREFIX:-""}
INSTANCE=${INSTANCE:-""}

if [[ -z "${IMAGE_PREFIX}" ]]; then
  echo -e "${RED}IMAGE_PREFIX is not set${NC}"
  [[ $0 == "$BASH_SOURCE" ]] && EXIT="exit" || EXIT="return"
  ${EXIT} 1
fi

if [[ -z "${INSTANCE}" ]]; then
  echo -e "${RED}INSTANCE is not set${NC}"
  [[ $0 == "$BASH_SOURCE" ]] && EXIT="exit" || EXIT="return"
  ${EXIT} 1
fi

if [[ -z "${ENV_VARS_FILE}" ]]; then
  echo -e "${RED}ENV_VARS_FILE is not set${NC}"
  [[ $0 == "$BASH_SOURCE" ]] && EXIT="exit" || EXIT="return"
  ${EXIT} 1
fi

if [[ ! -f "${ENV_VARS_FILE}" ]]; then
  echo -e "${RED}${ENV_VARS_FILE} does not exist${NC}"
  [[ $0 == "$BASH_SOURCE" ]] && EXIT="exit" || EXIT="return"
  ${EXIT} 1
fi

PYTHON_VERSION=$(cat .python-version)
IMAGE="${IMAGE_PREFIX}-${PYTHON_VERSION}"

docker build -t "${IMAGE}" \
  --build-arg "PYTHON_VERSION=${PYTHON_VERSION}" \
  "${PROJ_PATH}/scripts/ci/docker"

# Absolutely stomp on any existing instance
docker rm --force "${INSTANCE}" || true

run() {
  ENV_VARS_FILE=$(realpath "${ENV_VARS_FILE}")

  docker run \
    --rm \
    --name "${INSTANCE}" \
    --volume "${PROJ_PATH}:${PROJECT_RO_PATH}:ro" \
    --volume "${ENV_VARS_FILE}:/home/root/env.yml:ro" \
    --workdir "${PROJECT_RO_PATH}" \
    --env "PROJECT_RO_PATH=${PROJECT_RO_PATH}" \
    --env "PROJECT_CLONE_PATH=${PROJECT_CLONE_PATH}" \
    --env "ENV_VARS_FILE=/home/root/env.yml" \
    "${IMAGE}" \
    /bin/bash -c "${PROJECT_RO_PATH}/scripts/run-inside-ci.sh"
}

if run; then
  echo -e "${GREEN}Successfully ran inside docker${NC}"
  [[ $0 == "${BASH_SOURCE}" ]] && EXIT="exit" || EXIT="return"
  ${EXIT} 0
else
  echo -e "${RED}Failed!${NC}"
  [[ $0 == "${BASH_SOURCE}" ]] && EXIT="exit" || EXIT="return"
  ${EXIT} 1
fi
