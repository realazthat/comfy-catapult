#!/bin/bash
# https://gist.github.com/mohanpedala/1e2ff5661761d3abd0385e8223e16425
set -e -x -v -u -o pipefail

SCRIPT_DIR=$(realpath "$(dirname "${BASH_SOURCE[0]}")")
source "${SCRIPT_DIR}/common.sh"



# E.g https://github.com/realazthat/snipinator.
REPO_URL=$(git remote get-url origin)
# E.g realazthat/snipinator.
REPO_NAME=$(python -c 'from urllib.parse import urlparse; from pathlib import PurePath; repo_url = "'"${REPO_URL}"'"; parsed_url = urlparse(repo_url); path = PurePath(parsed_url.path); print(f"{path.parts[-2]}/{path.stem}")')
# Compute project name in terms of REPO_NAME.
# e.g snipinator.
PROJECT_NAME=$(basename "${REPO_NAME}")

TWINE_ENV_FILE=${TWINE_ENV_FILE:-"${HOME}/project-configs.yaml"}

# Example: v0.1.0
GIT_TAG=${GIT_TAG:-}
IMAGE_TAG=${IMAGE_TAG:-}

if [[ -z "${REPO_URL}" ]]; then
  echo -e "${RED}REPO_URL is not set${NC}"
  exit 1
fi

if [[ -z "${REPO_NAME}" ]]; then
  echo -e "${RED}REPO_NAME is not set${NC}"
  exit 1
fi

if [[ -z "${PROJECT_NAME}" ]]; then
  echo -e "${RED}PROJECT_NAME is not set${NC}"
  exit 1
fi

if [[ -z "${GIT_TAG}" ]]; then
  echo -e "${RED}GIT_TAG is not set${NC}"
  exit 1
fi

TMP_DIR=$(mktemp -d)
trap 'rm -rf "${TMP_DIR}"' EXIT

git clone "${REPO_URL}" "${TMP_DIR}/project"
cd "${TMP_DIR}/project"
git checkout "${GIT_TAG}"


VENV_PATH=${PWD}/.cache/scripts/.venv source "${PROJ_PATH}/scripts/utilities/ensure-venv.sh"
TOML=${PROJ_PATH}/pyproject.toml EXTRA=dev \
  DEV_VENV_PATH="${PWD}/.cache/scripts/.venv" \
  TARGET_VENV_PATH="${PWD}/.cache/scripts/.venv" \
  bash "${PROJ_PATH}/scripts/utilities/ensure-reqs.sh"


# if TWINE_USERNAME and TWINE_PASSWORD are not set:
if [[ -z "${TWINE_USERNAME:-}" ]] || [[ -z "${TWINE_PASSWORD:-}" ]]; then
  PROJECT_NAME=$(tomlq -r -e '.["project"]["name"]' "${PROJ_PATH}/pyproject.toml")

  TWINE_USERNAME=$(python -m yq -r '.["'"${PROJECT_NAME}"'"]["pypi"]["username"]' "${TWINE_ENV_FILE}")
  TWINE_PASSWORD=$(python -m yq -r '.["'"${PROJECT_NAME}"'"]["pypi"]["password"]' "${TWINE_ENV_FILE}")
  export TWINE_USERNAME
  export TWINE_PASSWORD
fi
if [[ "${TWINE_USERNAME}" = "null" ]] || [[ "${TWINE_PASSWORD}" = "null" ]]; then
  echo "Error: TWINE_USERNAME or TWINE_PASSWORD is 'null'."
  exit 1
fi

rm -Rf dist
python -m build
twine upload dist/*
