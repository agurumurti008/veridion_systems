# .devcontainer/Dockerfile
# Pin uv + Python together for reproducibility across all collaborators/prebuilds.
# Bump this single line when you want to move to a new uv or Python version.
FROM ghcr.io/astral-sh/uv:0.11.26-python3.13-trixie-slim

ARG USERNAME=vscode
ARG USER_UID=1000
ARG USER_GID=$USER_UID

# Create the non-root user VS Code / Codespaces expects, and the OS packages
# needed to build common scientific-Python wheels (numpy/scipy/torch deps).
RUN groupadd --gid $USER_GID $USERNAME \
    && useradd --uid $USER_UID --gid $USER_GID -m -s /bin/bash $USERNAME \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
        git \
        curl \
        ca-certificates \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

USER $USERNAME

# Cache dir must be owned by the non-root user or uv sync will hit permission
# errors when Codespaces (or a prebuild) runs as vscode instead of root.
ENV UV_CACHE_DIR=/home/$USERNAME/.cache/uv
RUN mkdir -p $UV_CACHE_DIR

WORKDIR /workspaces