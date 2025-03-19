
# user
sudo usermod -u 99 vscode
sudo usermod -g 100 vscode
sudo usermod -s /bin/zsh vscode

# zsh
git clone https://github.com/zsh-users/zsh-autosuggestions /home/vscode/.oh-my-zsh/custom/plugins/zsh-autosuggestions
git clone --depth=1 https://github.com/romkatv/powerlevel10k.git /home/vscode/.oh-my-zsh/custom/themes/powerlevel10k
rm /home/vscode/.zshrc
ln -s  /workspaces/home-ops/.private/devcontainer/.zshrc /home/vscode/.zshrc
ln -s  /workspaces/home-ops/.private/devcontainer/.zsh_aliases /home/vscode/.zsh_aliases
ln -s  /workspaces/home-ops/.private/devcontainer/.p10k.zsh /home/vscode/.p10k.zsh

# k9s
wget https://github.com/derailed/k9s/releases/download/latest/k9s_Linux_amd64.tar.gz -O /tmp/k9s.tar.gz
tar -xzf /tmp/k9s.tar.gz -C /tmp
sudo mv /tmp/k9s /usr/local/bin/k9s
sudo chmod +x /usr/local/bin/k9s

# permissions
sudo chown -R vscode:vscode /home/vscode
sudo chmod 777 /home/vscode/.zshrc /home/vscode/.zsh_aliases /home/vscode/.p10k.zsh

# change user
echo 'if [[ $- == *i* && $USER == "root" ]]; then exec su - vscode; fi' >> /root/.zshrc

return 0