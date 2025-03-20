#!/bin/bash
set -ex  # Exit on error

# Update user `vscode` UID/GID
sudo usermod -u 99 vscode
sudo usermod -g 100 vscode
sudo usermod -s /bin/zsh vscode
sudo usermod -aG sudo vscode   # Ensure sudo access
echo "vscode ALL=(ALL) NOPASSWD:ALL" | sudo tee /etc/sudoers.d/vscode

# Fix ownership for existing files after UID/GID change
sudo find / -user 1000 -exec chown -h 99:100 {} \; 2>/dev/null || echo "chown failed, skipping"

# Fix VS Code settings
rm -f /root/.vscode-server/data/Machine/settings.json
ln -s /workspaces/home-ops/.devcontainer/settings.json /root/.vscode-server/data/Machine/settings.json
sudo chown -R vscode:vscode /root/.vscode-server

# Install ZSH plugins
git clone https://github.com/zsh-users/zsh-autosuggestions /home/vscode/.oh-my-zsh/custom/plugins/zsh-autosuggestions
git clone --depth=1 https://github.com/romkatv/powerlevel10k.git /home/vscode/.oh-my-zsh/custom/themes/powerlevel10k

# Ensure proper ZSH configuration
rm -f /home/vscode/.zshrc /home/vscode/.zsh_aliases /home/vscode/.p10k.zsh
ln -s /workspaces/home-ops/.private/devcontainer/.zshrc /home/vscode/.zshrc
ln -s /workspaces/home-ops/.private/devcontainer/.zsh_aliases /home/vscode/.zsh_aliases
ln -s /workspaces/home-ops/.private/devcontainer/.p10k.zsh /home/vscode/.p10k.zsh

# Install k9s
wget -q https://github.com/derailed/k9s/releases/download/v0.40.10/k9s_Linux_amd64.tar.gz -O /tmp/k9s.tar.gz
tar -xzf /tmp/k9s.tar.gz -C /tmp
sudo mv /tmp/k9s /usr/local/bin/k9s
sudo chmod +x /usr/local/bin/k9s

# Ensure permissions
sudo chown -R vscode:vscode /home/vscode
sudo chmod 777 /home/vscode/.zshrc /home/vscode/.zsh_aliases /home/vscode/.p10k.zsh

# Fix ownership of the workspace folder
sudo chown -R vscode:vscode /workspaces/home-ops

# Switch user
echo 'if [[ $- == *i* && $USER == "root" ]]; then exec su - vscode; fi' >> /root/.zshrc

exit 0
