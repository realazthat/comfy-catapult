#!/bin/bash
# https://gist.github.com/mohanpedala/1e2ff5661761d3abd0385e8223e16425
set -e -x -v -u -o pipefail

SCRIPT_DIR=$(realpath "$(dirname "${BASH_SOURCE[0]}")")
source "${SCRIPT_DIR}/utilities/common.sh"


EXTRA=dev bash scripts/utilities/pin-extra-reqs.sh
EXTRA=prod bash scripts/utilities/pin-extra-reqs.sh
bash scripts/format.sh
bash scripts/gen-readme.sh
bash scripts/run-all-tests.sh
bash scripts/run-all-examples.sh
if [[ -z "${GITHUB_ACTIONS:-}" ]]; then
	bash scripts/precommit.sh
  bash scripts/act.sh
fi
