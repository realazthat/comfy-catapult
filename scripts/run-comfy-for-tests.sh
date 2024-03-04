#!/bin/bash
# https://gist.github.com/mohanpedala/1e2ff5661761d3abd0385e8223e16425
set -e -x -v -u -o pipefail

SCRIPT_DIR=$(realpath "$(dirname "${BASH_SOURCE[0]}")")
source "${SCRIPT_DIR}/utilities/common.sh"

# COMFY_IMAGE_NAME=ghcr.io/ai-dock/comfyui:pytorch-2.1.2-py3.10-cuda-12.1.0-runtime-22.04
COMFY_IMAGE_NAME=ghcr.io/ai-dock/comfyui:pytorch-2.2.0-py3.10-cpu-22.04
# PROVISIONING_SCRIPT="${PWD}/scripts/provisioning-for-tests.sh"
COMFY_INSTANCE_NAME=${COMFY_INSTANCE_NAME:-comfy-test-instance}

# COMFY_PORT=${COMFY_PORT:-}
# if [[ -z "${COMFY_PORT}" ]]; then
#   echo -e "${RED}COMFY_PORT is not set${NC}"
#   exit 1
# fi

################################################################################
# Download the model checkpoint
CKPT_URL="https://huggingface.co/stabilityai/sdxl-turbo/resolve/main/sd_xl_turbo_1.0_fp16.safetensors"
CKPT_SHA256=e869ac7d6942cb327d68d5ed83a40447aadf20e0c3358d98b2cc9e270db0da26
CKPT_DIR="${PWD}/.cache/models-for-tests"
mkdir -p "${CKPT_DIR}"
CKPT_FILE="${CKPT_DIR}/sd_xl_turbo_1.0_fp16.safetensors"


if ! echo "${CKPT_SHA256}  ${CKPT_FILE}" | sha256sum --check --status; then
  echo -e "${YELLOW}Downloading checkpoint${NC}"
  mkdir -p $(dirname "${CKPT_FILE}")
  wget -q --continue --show-progress -e dotbytes="4M" -O "${CKPT_FILE}" "${CKPT_URL}"
  echo "${CKPT_SHA256}  ${CKPT_FILE}" | sha256sum --check --status
else
  echo -e "${GREEN}Checkpoint already downloaded${NC}"
fi

chmod a+wxr "${CKPT_FILE}"
chmod -R a+wxr "${CKPT_DIR}"
# chown 1000:1111 "${CKPT_FILE}"
ls -la "${CKPT_DIR}"
################################################################################

DOCKER_CKPT_DIR=/opt/ComfyUI/models/checkpoints
DOCKER_CKPT_FILE="${DOCKER_CKPT_DIR}/sd_xl_turbo_1.0_fp16.safetensors"


# -v "${PROVISIONING_SCRIPT}:/opt/ai-dock/bin/provisioning.sh" \

echo -e "${YELLOW}Stopping and removing existing comfy instance${NC}"
docker rm --force "${COMFY_INSTANCE_NAME}" || true
echo -e "${YELLOW}Starting comfy instance${NC}"

docker run -d --rm \
  -e COMFYUI_PORT=41112 \
  -e SERVICEPORTAL_PORT_HOST=41113 \
  -e WEB_PASSWORD=1 \
  -p "41111:1111" \
  -p "41112:41112" \
  -p "41113:41113" \
  --name "${COMFY_INSTANCE_NAME}" \
  "${COMFY_IMAGE_NAME}" \
  init.sh
docker cp "${CKPT_FILE}" "${COMFY_INSTANCE_NAME}:${DOCKER_CKPT_FILE}"
ls -la "${CKPT_DIR}"

docker exec "${COMFY_INSTANCE_NAME}" /bin/bash -c "ls -la ${DOCKER_CKPT_DIR}"
docker exec "${COMFY_INSTANCE_NAME}" /bin/bash -c "echo \"${CKPT_SHA256} ${DOCKER_CKPT_FILE}\" | sha256sum --check --status"

while ! curl -s "http://localhost:41112/system_stats" > /dev/null; do
  echo -e "${YELLOW}Waiting for comfy to start${NC}"
  sleep 1
done
echo -e "${GREEN}Comfy is ready${NC}"
