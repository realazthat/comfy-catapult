#!/bin/bash
# https://gist.github.com/mohanpedala/1e2ff5661761d3abd0385e8223e16425
set -e -x -v -u -o pipefail

UTILITIES_PATH="$(realpath "$(dirname "${BASH_SOURCE[0]}")")"

SCRIPTS_PATH=$(dirname "${UTILITIES_PATH}")
PROJ_PATH=$(dirname "${SCRIPTS_PATH}")
export PROJ_PATH

THIS_SCRIPT_DIRECTORY=$(dirname "${0}")
export THIS_SCRIPT_DIRECTORY

# UTILITIES_DIRECTORY=$(dirname "${THIS_SCRIPT_DIRECTORY}")

RED='\033[0;31m'
export RED
GREEN='\033[0;32m'
export GREEN
BLUE='\033[0;34m'
export BLUE
YELLOW='\033[0;33m'
export YELLOW
NC='\033[0m' # No Color
export NC
