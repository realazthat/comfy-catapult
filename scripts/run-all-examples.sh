#!/bin/bash

# https://gist.github.com/mohanpedala/1e2ff5661761d3abd0385e8223e16425
set -e -x -v -u -o pipefail

SCRIPT_DIR=$(realpath "$(dirname "${BASH_SOURCE[0]}")")
source "${SCRIPT_DIR}/utilities/common.sh"

export COMFY_API_URL=${COMFY_API_URL:-""}

if [[ -z "${COMFY_API_URL}" ]]; then
  echo -e "${RED}COMFY_API_URL is not set${NC}"
  [[ $0 == "${BASH_SOURCE[0]}" ]] && EXIT="exit" || EXIT="return"
  ${EXIT} 1
fi

export COMFY_INSTALL_FILE_URL=${COMFY_INSTALL_FILE_URL:-""}

VENV_PATH=${PWD}/.venv source "${PROJ_PATH}/scripts/utilities/ensure-venv.sh"
TOML=${PROJ_PATH}/pyproject.toml EXTRA=prod \
  DEV_VENV_PATH="${PWD}/.cache/scripts/.venv" \
  TARGET_VENV_PATH="${PWD}/.venv" \
  bash "${PROJ_PATH}/scripts/utilities/ensure-reqs.sh"


export PYTHONPATH=${PYTHONPATH:-}
export PYTHONPATH=${PYTHONPATH}:${PWD}

################################################################################
python -m examples.using_pydantic
################################################################################
python -m examples.add_a_node
################################################################################
ARGS=(
  "--comfy_install_file_url" "${COMFY_INSTALL_FILE_URL}"
  "--comfy_api_url" "${COMFY_API_URL}"
  "--tmp_path" "${PWD}/.deleteme/tmp/"
  "--output_path" "${PWD}/.deleteme/output.png"
  "--positive_prompt" "amazing cloudscape, towering clouds, thunderstorm, awe"
  "--negative_prompt" "dull, blurry, nsfw"
)

if [[ -n "${API_WORKFLOW_JSON_PATH-}" ]]; then
  ARGS+=("--api_workflow_json_path" "${API_WORKFLOW_JSON_PATH}")
fi

if [[ -n "${CHECKPOINT_NAME-}" ]]; then
  ARGS+=("--ckpt_name" "${CHECKPOINT_NAME}")
fi
python -m examples.sdxlturbo_example_catapulter "${ARGS[@]}"

# if tiv is a valid command
if command -v tiv &> /dev/null; then
  tiv -w 80 -h 80 "${PWD}/.deleteme/output.png"
fi
################################################################################
python -m comfy_catapult.cli --help
################################################################################

# For each sh in examples
find examples -type f -name "*.sh" -print0 | while IFS= read -r -d '' EXAMPLE; do
  bash "${EXAMPLE}"
  echo -e "${GREEN}${EXAMPLE} ran successfully${NC}"
done

echo -e "${GREEN}All examples ran successfully${NC}"
