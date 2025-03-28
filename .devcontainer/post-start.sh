#!/bin/bash
set -ex  # Exit on error

# Ensure user `vscode` UID/GID are correct
if [[ $(id -u vscode) -ne 99 || $(id -g vscode) -ne 100 ]]; then
    sudo usermod -u 99 vscode
    sudo usermod -g 100 vscode
    sudo usermod -s /bin/zsh vscode
    echo "vscode ALL=(ALL) NOPASSWD:ALL" | sudo tee /etc/sudoers.d/vscode
fi

# Fix ownership for existing files after UID/GID change
# sudo find / -user 1000 -exec chown -h 99:100 {} \; 2>/dev/null || echo "chown failed, skipping"

# Fix VS Code settings if the symlink doesn't exist
if [ ! -L /root/.vscode-server/data/Machine/settings.json ]; then
    rm -f /root/.vscode-server/data/Machine/settings.json
    ln -s /workspaces/home-ops/.devcontainer/settings.json /root/.vscode-server/data/Machine/settings.json
    sudo chown -R vscode:vscode /root/.vscode-server
fi

# Install ZSH plugins if not already installed
if [ ! -d "/home/vscode/.oh-my-zsh/custom/plugins/zsh-autosuggestions" ]; then
    git clone https://github.com/zsh-users/zsh-autosuggestions /home/vscode/.oh-my-zsh/custom/plugins/zsh-autosuggestions
fi

if [ ! -d "/home/vscode/.oh-my-zsh/custom/themes/powerlevel10k" ]; then
    git clone --depth=1 https://github.com/romkatv/powerlevel10k.git /home/vscode/.oh-my-zsh/custom/themes/powerlevel10k
fi

# Ensure proper ZSH configuration if symlinks are missing
if [ ! -L /home/vscode/.zshrc ]; then
    rm -f /home/vscode/.zshrc /home/vscode/.zsh_aliases /home/vscode/.p10k.zsh
    ln -s /workspaces/home-ops/.private/devcontainer/.zshrc /home/vscode/.zshrc
    ln -s /workspaces/home-ops/.private/devcontainer/.zsh_aliases /home/vscode/.zsh_aliases
    ln -s /workspaces/home-ops/.private/devcontainer/.p10k.zsh /home/vscode/.p10k.zsh
fi

# Install k9s only if not already installed
if ! command -v k9s &> /dev/null; then
    wget -q https://github.com/derailed/k9s/releases/download/v0.40.10/k9s_Linux_amd64.tar.gz -O /tmp/k9s.tar.gz
    tar -xzf /tmp/k9s.tar.gz -C /tmp
    sudo mv /tmp/k9s /usr/local/bin/k9s
    sudo chmod +x /usr/local/bin/k9s
fi

# Ensure the correct permissions for files and directories
sudo chown -R vscode:vscode /home/vscode
sudo chmod 777 /home/vscode/.zshrc /home/vscode/.zsh_aliases /home/vscode/.p10k.zsh

# Fix ownership of the workspace folder only if necessary
if [[ $(stat -c '%U' /workspaces/home-ops) != "vscode" ]]; then
    sudo chown -R vscode:vscode /workspaces/home-ops
fi

# Switch user to `vscode` for further commands
echo 'if [[ $- == *i* && $USER == "root" ]]; then exec su - vscode; fi' >> /root/.zshrc

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

# Symlink zsh history file if not already linked
if [ ! -L ~/.zsh_history ]; then
    ln -sf /workspaces/home-ops/.private/zsh_history ~/.zsh_history
fi

exit 0
