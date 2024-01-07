# https://gist.github.com/mohanpedala/1e2ff5661761d3abd0385e8223e16425
set -e -x -v -u -o pipefail

SCRIPT_DIR=$(realpath "$(dirname "${BASH_SOURCE[0]}")")
source "$SCRIPT_DIR/common.sh"

export COMFY_DIRECTORY=${COMFY_DIRECTORY:-""}

if [ -z "$COMFY_DIRECTORY" ]; then
  echo -e "${RED}COMFY_DIRECTORY is not set${NC}"
  [[ $0 == "$BASH_SOURCE" ]] && EXIT=exit || EXIT=return
  $EXIT 1
fi

if [[ ! $COMFY_DIRECTORY =~ /ComfyUI$ ]]; then
  echo -e "${RED}COMFY_DIRECTORY must end with /ComfyUI${NC}"
  [[ $0 == "$BASH_SOURCE" ]] && EXIT=exit || EXIT=return
  $EXIT 1
fi

COMFY_DIRECTORY=$(realpath -m "$COMFY_DIRECTORY")

if [ -d "$COMFY_DIRECTORY" ]; then
  echo -e "${RED}${COMFY_DIRECTORY} already exists${NC}"
  [[ $0 == "$BASH_SOURCE" ]] && EXIT=exit || EXIT=return
  $EXIT 1
fi

PARENT_DIRECTORY=$(dirname "$COMFY_DIRECTORY")

VENV_PATH="${VENV_PATH:-$COMFY_DIRECTORY/.venv}"

if [ -z "$VENV_PATH" ]; then
  echo -e "${RED}VENV_PATH is not set${NC}"
  [[ $0 == "$BASH_SOURCE" ]] && EXIT=exit || EXIT=return
  $EXIT 1
fi

################################################################################

mkdir -p "$PARENT_DIRECTORY"

cd "$PARENT_DIRECTORY"
git clone https://github.com/comfyanonymous/ComfyUI.git

cd "$COMFY_DIRECTORY"
cp "$PROJECT_DIRECTORY/.python-version" .python-version

source "$PROJ_PATH/scripts/utilities/ensure-venv.sh"

# pip uninstall torch
pip install torch torchvision torchaudio --extra-index-url https://download.pytorch.org/whl/cu121
# pip install --pre torch torchvision torchaudio --index-url https://download.pytorch.org/whl/nightly/cu121
# pip install torch-directml
pip install -r requirements.txt
