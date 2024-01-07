# https://gist.github.com/mohanpedala/1e2ff5661761d3abd0385e8223e16425
set -e -x -v -u -o pipefail

UTILITIES_PATH="$(realpath "$(dirname "${BASH_SOURCE[0]}")")"

SCRIPTS_PATH=$(dirname $UTILITIES_PATH)
export PROJ_PATH=$(dirname $SCRIPTS_PATH)

export THIS_SCRIPT_DIRECTORY=$(dirname $0)
UTILITIES_DIRECTORY=$(dirname $THIS_SCRIPT_DIRECTORY)

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color
