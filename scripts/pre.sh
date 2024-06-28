#!/bin/bash
# https://gist.github.com/mohanpedala/1e2ff5661761d3abd0385e8223e16425
set -e -x -v -u -o pipefail

SCRIPT_DIR=$(realpath "$(dirname "${BASH_SOURCE[0]}")")
source "${SCRIPT_DIR}/utilities/common.sh"

export TOML="${PROJ_PATH}/pyproject.toml"

# This variable will be 1 when we are the ideal version in the GH action matrix.
IDEAL="0"
PYTHON_VERSION=$(cat .python-version)
if [[ "${PYTHON_VERSION}" == "3.8.0" ]]; then
  IDEAL="1"
fi

if [[ -z "${GITHUB_ACTIONS:-}" ]]; then
  if [[ "${IDEAL}" != "1" ]]; then
    echo -e "${RED}Somehow we are not 'ideal' outside of GH Action workflow. IDEAL is meant to be 1 when we are running the GH Action matrix configuration that matches the configuration outside of the GH Action workflow. But we are not in the GH Action workflow, yet it is not 1!${NC}"
    exit 1
  fi
fi

# Check that no changes occurred to files through the workflow.
if [[ "${IDEAL}" == "1" ]]; then
  STEP=pre bash scripts/utilities/changeguard.sh
fi

EXTRA=dev bash scripts/utilities/pin-extra-reqs.sh
EXTRA=prod bash scripts/utilities/pin-extra-reqs.sh
bash scripts/run-all-tests.sh
bash scripts/run-all-examples.sh
bash scripts/type-check.sh
bash scripts/generate.sh
if [[ -z "${GITHUB_ACTIONS:-}" ]]; then
  bash scripts/act.sh
	bash scripts/precommit.sh
fi

# Check that no changes occurred to files throughout pre.sh to tracked files. If
# changes occurred, they should be staged and pre.sh should be run again.
if [[ "${IDEAL}" == "1" ]]; then
  STEP=post bash scripts/utilities/changeguard.sh
fi
