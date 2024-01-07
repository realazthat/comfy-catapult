# https://gist.github.com/mohanpedala/1e2ff5661761d3abd0385e8223e16425
set -e -x -v -u -o pipefail

################################################################################
SCRIPT_DIR=$(realpath "$(dirname "${BASH_SOURCE[0]}")")
source $SCRIPT_DIR/utilities/common.sh

VENV_PATH=.cache/scripts/.venv source $PROJ_PATH/scripts/utilities/ensure-venv.sh
REQS=$PROJ_PATH/scripts/requirements-dev.txt source $PROJ_PATH/scripts/utilities/ensure-reqs.sh
################################################################################
TEMPLATE=README.template.md
################################################################################
chmod 644 README.md

echo "<!-- WARNING: This file is auto-generated. Do not edit directly.             -->" >README.md
echo '<!-- SOURCE: `README.template.md`.                                           -->' >>README.md

python "$PROJ_PATH/scripts/utilities/gen-readme.py" README.template.md >>README.md
chmod 444 README.md
################################################################################
