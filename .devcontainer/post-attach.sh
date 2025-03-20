#!/bin/bash
set -e  # Exit on error

# Run commands as `vscode` user
sudo -u vscode bash << EOF
    export GITHUB_TOKEN=${GITHUB_TOKEN}
    export MISE_GLOBAL_CONFIG_ROOT=/workspaces/home-ops/
    cd /workspaces/home-ops
    mise trust
    mise exec python@3 -- python -m ensurepip --default-pip
    mise exec python@3 -- ~/.local/share/mise/shims/pip install pipx
    mise install
    git config --global --add safe.directory /workspaces/home-ops
EOF

exit 0
