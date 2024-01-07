# https://gist.github.com/mohanpedala/1e2ff5661761d3abd0385e8223e16425
set -e -x -v -u -o pipefail

SCRIPT_DIR=$(realpath "$(dirname "${BASH_SOURCE[0]}")")
source $SCRIPT_DIR/utilities/common.sh

export COMFY_API_URL=${COMFY_API_URL:-""}

if [ -z "$COMFY_API_URL" ]; then
  echo -e "${RED}COMFY_API_URL is not set${NC}"
  [[ $0 == "$BASH_SOURCE" ]] && EXIT=exit || EXIT=return
  $EXIT 1
fi

VENV_PATH=$PWD/.venv source $PROJ_PATH/scripts/utilities/ensure-venv.sh

export PYTHONPATH=${PYTHONPATH:-}
export PYTHONPATH=$PYTHONPATH:$PWD

# Find all files in comfy_catapult that end in _test.py
find comfy_catapult -name "*_test.py" | while read -r test_file; do
  echo "Running $test_file"
  python "$test_file"
done
