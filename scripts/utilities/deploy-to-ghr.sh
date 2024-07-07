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

if [[ -z "${IMAGE_TAG}" ]]; then
  echo -e "${RED}IMAGE_TAG is not set${NC}"
  exit 1
fi

TMP_DIR=$(mktemp -d)
trap 'rm -rf "${TMP_DIR}"' EXIT

git clone "${REPO_URL}" "${TMP_DIR}/project"
cd "${TMP_DIR}/project"
git checkout "${GIT_TAG}"

cp "${PROJ_PATH}/Dockerfile" .

docker build \
  --tag "${PROJECT_NAME}:${IMAGE_TAG}" \
  --label "org.opencontainers.image.source=https://github.com/${REPO_NAME}" \
  .

docker run --rm -it \
  --name "${PROJECT_NAME}-instance" \
  "${PROJECT_NAME}:${IMAGE_TAG}"

docker tag "${PROJECT_NAME}:${IMAGE_TAG}" "ghcr.io/${REPO_NAME}:${IMAGE_TAG}"

docker push "ghcr.io/${REPO_NAME}:${IMAGE_TAG}"
