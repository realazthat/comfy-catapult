#!/bin/bash
# https://gist.github.com/mohanpedala/1e2ff5661761d3abd0385e8223e16425
set -e -x -v -u -o pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color
export RED GREEN NC

if [[ -z "${PYTHON_VERSION}" ]]; then
	echo -e "${RED}PYTHON_VERSION is not set${NC}"
	[[ $0 == "${BASH_SOURCE[0]}" ]] && EXIT="exit" || EXIT="return"
	${EXIT} 1
fi

# Update and Upgrade the system
apt-get update -y && apt-get upgrade -y

# Install necessary basic tools
apt-get install -y git curl wget build-essential

ln -fs /usr/share/zoneinfo/UTC /etc/localtime

# Install dependencies for pyenv and Python build
apt-get install -y make libssl-dev zlib1g-dev libbz2-dev \
	libreadline-dev libsqlite3-dev llvm libncurses5-dev libncursesw5-dev \
	xz-utils tk-dev libffi-dev liblzma-dev

################################################################################
YQ_VER=v4.40.5
YQ_BIN=yq_linux_amd64
YQ_URL="https://github.com/mikefarah/yq/releases/download/${YQ_VER}/${YQ_BIN}"
wget "${YQ_URL}" -O /usr/bin/yq && chmod +x /usr/bin/yq
################################################################################

# Install pyenv
curl https://pyenv.run | bash

# Set environment variables for Pyenv and add them to .profile
echo 'export PYENV_ROOT="$HOME/.pyenv"' >>~/.profile
echo 'export PATH="$PYENV_ROOT/bin:$PATH"' >>~/.profile

# Initialize Pyenv and Pyenv-Virtualenv and add them to .profile
echo 'if command -v pyenv 1>/dev/null 2>&1; then' >>~/.profile
echo '    eval "$(pyenv init --path)"' >>~/.profile
echo '    eval "$(pyenv virtualenv-init -)"' >>~/.profile
echo 'fi' >>~/.profile

################################################################################
# Pre-install required python version.

PYENV_ROOT="${HOME}/.pyenv"
PATH="${PYENV_ROOT}/bin:${PATH}"
eval "$(pyenv init --path)"
eval "$(pyenv virtualenv-init -)"

pyenv install --skip-existing "${PYTHON_VERSION}"
################################################################################

# Clean up APT when done.
apt-get clean && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

echo "Prerequisites installed."
