#!/bin/bash
sudo apt update
sudo apt install -y pipx python3-venv
pipx ensurepath   # reopen terminal if it suggests PATH changes

echo "Applying PATH changes..."
source ~/.bashrc

echo "Installing dkinst via pipx..."
pipx install dkinst

source ~/.bashrc
dkinst prereqs

echo "dkinst installation complete. You can now run 'dkinst' from the command line."
echo "To update dkinst in the future, run: pipx upgrade dkinst"
echo "To uninstall dkinst, run: pipx uninstall dkinst"
echo "To run dkinst in current session, restart your terminal or run: source ~/.bashrc"