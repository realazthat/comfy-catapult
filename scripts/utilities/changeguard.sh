#!/bin/bash
# This script is used to check that no changes occur to files through the act
# workflow. If changes occurred, they should have been staged. This is usually
# run after a `git checkout-index --all` which extracts all the staged files,
# and before the main body of `pre.sh`.

# https://gist.github.com/mohanpedala/1e2ff5661761d3abd0385e8223e16425
set -e -x -v -u -o pipefail

SCRIPT_DIR=$(realpath "$(dirname "${BASH_SOURCE[0]}")")
source "${SCRIPT_DIR}/common.sh"

VENV_PATH="${PWD}/.cache/scripts/.venv" source "${PROJ_PATH}/scripts/utilities/ensure-venv.sh"
TOML=${PROJ_PATH}/pyproject.toml EXTRA=dev \
  DEV_VENV_PATH="${PWD}/.cache/scripts/.venv" \
  TARGET_VENV_PATH="${PWD}/.cache/scripts/.venv" \
  bash "${PROJ_PATH}/scripts/utilities/ensure-reqs.sh"

STEP=${STEP:-}

METHOD=${METHOD:-auto}
AUDIT_FILE=${AUDIT_FILE:-"${PWD}/.cache/scripts/check-changes-audit.yaml"}
AUDIT_LOG=${AUDIT_LOG:-"${PWD}/.cache/scripts/check-changes-audit.log"}

function do_hash() {
  python -m changeguard.cli hash \
    --ignorefile "${PROJ_PATH}/.gitignore" \
    --ignoreline .trunk --ignoreline .git \
    --method "${METHOD}" \
    --tmp-backup-dir "${PWD}/.cache/scripts/audit-original" \
    --audit-file "${AUDIT_FILE}" \
    --directory "${PROJ_PATH}"
}

function do_audit() {
  python -m changeguard.cli audit \
    --audit-file "${AUDIT_FILE}" \
    --show-delta \
    --directory "${PROJ_PATH}" 2>&1 | tee "${AUDIT_LOG}"
}

if [[ "${STEP}" == "pre" ]]; then
  do_hash
  echo -e "${GREEN}Hashes generated, saved to ${AUDIT_FILE}${NC}"
elif [[ "${STEP}" == "post" ]]; then
  # trunk-ignore(shellcheck/SC2310)
  if do_audit; then
    echo -e "${GREEN}No changes occurred during the workflow${NC}"
  else
    echo -e "${RED}Error auditing files.${NC}"
    echo -e "${RED}If a post-stage change occurred, you can ignore it by adding it to ${PROJ_PATH}/.gitignore or ${PROJ_PATH}/.changeguard-gitignore.${NC}"
    exit 1
  fi
else
  echo -e "${RED}Error: STEP must be set to 'pre' or 'post'${NC}"
  exit 1
fi
