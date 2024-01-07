# https://gist.github.com/mohanpedala/1e2ff5661761d3abd0385e8223e16425
set -e -x -v -u -o pipefail

SCRIPT_DIR=$(realpath "$(dirname "${BASH_SOURCE[0]}")")
source "$SCRIPT_DIR/common.sh"

REQS=${REQS:-""}

if [ -z "$REQS" ]; then
  echo -e "${RED}REQS is not set${NC}"
  [[ $0 == "$BASH_SOURCE" ]] && EXIT=exit || EXIT=return
  $EXIT 1
fi

# Better way to Check if pip-sync is installed

if which pip-sync; then
  echo "pip-sync is installed"
else
  echo "pip-sync is not installed"
  pip install pip-tools
fi

pip-sync "$REQS"
# pip install -r "$REQS"
# pip install --no-deps --ignore-installed -r "$REQS"
