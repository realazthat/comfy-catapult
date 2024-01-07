# https://gist.github.com/mohanpedala/1e2ff5661761d3abd0385e8223e16425
set -e -x -v -u -o pipefail

source scripts/utilities/common.sh

AM_I_INSIDE_DOCKER="${AM_I_INSIDE_DOCKER:-}"
PROJECT_ROOT_INSIDE=/comfy_catapult
PROJECT_ROOT_OUTSIDE="$(pwd)"

UBUNTU_IMAGE="ubuntu:20.04"
INSTANCE_NAME="comfy-catapult"

echo -e "${GREEN}Running inside docker${NC}"

if [ "$AM_I_INSIDE_DOCKER" = "false" ]; then
	echo -e "${GREEN}Running outside docker${NC}"
	# Absolutely stomp on any existing instance
	docker rm --force "$INSTANCE_NAME" || true

	docker run \
		--rm \
		--name "$INSTANCE_NAME" \
		--interactive \
		--tty \
		--volume "$PROJECT_ROOT_OUTSIDE:$PROJECT_ROOT_INSIDE" \
		--workdir "$PROJECT_ROOT_INSIDE" \
		$UBUNTU_IMAGE \
		/bin/bash -c "AM_I_INSIDE_DOCKER=true ./scripts/run-tests.sh"
	return 0
fi
