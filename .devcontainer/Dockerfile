FROM mcr.microsoft.com/devcontainers/base:ubuntu-22.04

RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y \
    python3 python3-venv python3-pip \
    postgresql-client \
    curl git ca-certificates build-essential \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /workspaces/carp_v2
