#!/bin/bash

# https://gist.github.com/mohanpedala/1e2ff5661761d3abd0385e8223e16425
set -e -x -v -u -o pipefail

SCRIPT_DIR=$(realpath "$(dirname "${BASH_SOURCE[0]}")")
source "${SCRIPT_DIR}/utilities/common.sh"

export COMFY_API_URL=${COMFY_API_URL:-""}

if [[ -z "${COMFY_API_URL}" ]]; then
  echo -e "${RED}COMFY_API_URL is not set${NC}"
  # trunk-ignore(shellcheck/SC2128)
  # trunk-ignore(shellcheck/SC2209)
  [[ $0 == "${BASH_SOURCE}" ]] && EXIT=exit || EXIT=return
  ${EXIT} 1
fi

export COMFY_INSTALL_FILE_URL=${COMFY_INSTALL_FILE_URL:-""}

VENV_PATH="${PWD}/.venv" source "${PROJ_PATH}/scripts/utilities/ensure-venv.sh"

export PYTHONPATH=${PYTHONPATH:-}
export PYTHONPATH=${PYTHONPATH}:${PWD}

python examples/using_pydantic.py
python examples/add_a_node.py

ARGS=(
  "--comfy_install_file_url" "${COMFY_INSTALL_FILE_URL}"
  "--comfy_api_url" "${COMFY_API_URL}"
  "--tmp_path" "${PWD}/.deleteme/tmp/"
  "--output_path" "${PWD}/.deleteme/output.png"
  "--positive_prompt" "amazing cloudscape, towering clouds, thunderstorm, awe"
  "--negative_prompt" "dull, blurry, nsfw"
)

if [[ -n "${CHECKPOINT_NAME-}" ]]; then
  ARGS+=("--ckpt_name" "${CHECKPOINT_NAME}")
fi
python examples/sdxlturbo_example_catapulter.py "${ARGS[@]}"


echo -e "${GREEN}All examples ran successfully${NC}"
