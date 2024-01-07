# https://gist.github.com/mohanpedala/1e2ff5661761d3abd0385e8223e16425
set -e -x -v -u -o pipefail

source "$PROJ_PATH/scripts/utilities/common.sh"

export COMFY_API_URL=${COMFY_API_URL:-""}

if [ -z "$COMFY_API_URL" ]; then
	echo -e "${RED}COMFY_API_URL is not set${NC}"
	return 1
fi

TEMPORARY_DIRECTORY=$(mktemp -d)

bash "$PROJ_PATH/scripts/ensure-pyenv.sh"

python -m venv $TEMPORARY_DIRECTORY/.venv
source $TEMPORARY_DIRECTORY/.venv/bin/activate

pip install -r "$PROJ_PATH/scripts/requirements.txt"

# Smoke test
bash "$PROJ_PATH/scripts/run-all-examples.sh"

# Clean up.
rm -Rf $TEMPORARY_DIRECTORY
