# https://gist.github.com/mohanpedala/1e2ff5661761d3abd0385e8223e16425
set -e -x -v -u -o pipefail

SCRIPT_DIR=$(realpath "$(dirname "${BASH_SOURCE[0]}")")
source "$SCRIPT_DIR/common.sh"

EXPECTED_PYTHON_VERSION=$(cat $PWD/.python-version)
# Get ONLY the version number, not the whole string
PYTHON_VERSION=$(python -c "import sys; print(sys.version.split()[0])")

if [ "$PYTHON_VERSION" != "$EXPECTED_PYTHON_VERSION" ]; then
  echo -e "${RED}Expected python version $EXPECTED_PYTHON_VERSION, got $PYTHON_VERSION${NC}"
  [[ $0 == "$BASH_SOURCE" ]] && EXIT=exit || EXIT=return
  $EXIT 1
fi
