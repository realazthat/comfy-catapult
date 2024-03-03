#!/bin/bash

# https://gist.github.com/mohanpedala/1e2ff5661761d3abd0385e8223e16425
set -e -x -v -u -o pipefail

SCRIPT_DIR=$(realpath "$(dirname "${BASH_SOURCE[0]}")")
source "${SCRIPT_DIR}/utilities/common.sh"

CACHE_SERVER_PATH="${PWD}/.cache/act/cache-server-path"
ACTION_CACHE_PATH="${PWD}/.cache/act/action-cache"
ACT_PROJECT_PATH="${PWD}/.cache/act/project-clone-path"
mkdir -p "${CACHE_SERVER_PATH}"
mkdir -p "${ACTION_CACHE_PATH}"
mkdir -p "${ACT_PROJECT_PATH}"

# Make it readable and deletable
chmod -R 777 "${ACT_PROJECT_PATH}" || true
rm -Rf "${ACT_PROJECT_PATH}" || true
mkdir -p "${ACT_PROJECT_PATH}"
git checkout-index --all --prefix="${ACT_PROJECT_PATH}/"
# Set .act-project-path to read-only
chmod -R 555 "${ACT_PROJECT_PATH}"
cd "${ACT_PROJECT_PATH}"
go run github.com/nektos/act@c79f59f802673f00911bea93db15b83f5bf3507b \
  push \
  --use-new-action-cache \
  --cache-server-path "${CACHE_SERVER_PATH}" \
  --action-cache-path "${ACTION_CACHE_PATH}" \
  --job build-and-test
