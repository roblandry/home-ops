
# su vscode
# cd /workspaces/home-ops
# mise trust -a
# mise use -g python@3
# mise use kubecolor

su vscode << EOF
    cd /workspaces/home-ops
    mise trust
    pip install pipx
    mise install
EOF

return 0