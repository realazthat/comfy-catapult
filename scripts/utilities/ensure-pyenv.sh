# https://gist.github.com/mohanpedala/1e2ff5661761d3abd0385e8223e16425
set -e -x -v -u -o pipefail

SCRIPT_DIR=$(realpath "$(dirname "${BASH_SOURCE[0]}")")
source $SCRIPT_DIR/common.sh

# Make sure .python-version exists.
if [ ! -f $PWD/.python-version ]; then
  [[ $0 == "$BASH_SOURCE" ]] && EXIT=exit || EXIT=return
  echo -e "${RED}.python-version does not exist in $PWD${NC}"
  $EXIT 1
fi

export PYENV_ROOT="$HOME/.pyenv"
export PATH="$PYENV_ROOT/bin:$PATH"
eval "$(pyenv init --path)"
eval "$(pyenv virtualenv-init -)"

pyenv install --skip-existing

source "$PROJ_PATH/scripts/utilities/ensure-py-version.sh"
