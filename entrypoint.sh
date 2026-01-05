#!/bin/bash

# Ensure git is installed
if ! command -v git &> /dev/null; then
  apt-get update
  apt-get install -y git
fi


if ! command -v sqlite3 &> /dev/null; then
  apt-get update
  apt-get install -y sqlite3 libsqlite3-dev
fi


# Ensure docker is installed
if ! command -v docker &> /dev/null; then
  apt-get update
  apt-get install -y \
    ca-certificates \
    curl \
    gnupg \
    lsb-release

  curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg

  echo \
    "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu \
    $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null

  apt-get update
  apt-get install -y docker-ce docker-ce-cli containerd.io
fi

# Ensure docker-compose is installed
if ! command -v docker-compose &> /dev/null; then
  curl -L "https://github.com/docker/compose/releases/download/1.29.2/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
  chmod +x /usr/local/bin/docker-compose
fi

# Ensure the docker group exists
if ! getent group docker > /dev/null; then
  groupadd docker
  usermod -aG docker $USER
fi

# Execute the command passed to the container
exec "$@"
