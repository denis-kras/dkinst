from typing import Literal

from rich.console import Console

from . import _base
from .helpers.infra import commands


console = Console()


class GoogleChrome(_base.BaseInstaller):
    def __init__(self):
        super().__init__(__file__)
        self.description: str = "Google Chrome Installer"
        self.version: str = "1.0.0"
        self.platforms: list = ["debian"]
        self.admins: dict = {"debian": ["install"]}

    def install(
            self,
    ) -> int:
        return install_function()

    def _show_help(
            self,
            method: Literal["install", "uninstall", "upgrade"]
    ) -> None:
        if method == "install":
            method_help: str = (
                "This method installs Google Chrome deb file from its official URL.\n"
                "After installation, patches the .desktop file to use --password-store=basic,\n"
                "which prevents the 'Unlock Login Keyring' dialog on systems without auto-unlock.\n"
            )
            print(method_help)
        else:
            raise ValueError(f"Unknown method '{method}'.")


def install_function():
    script_lines = [
        """
DEB_PATH="/tmp/google-chrome-stable_current_amd64.deb"
wget -O "$DEB_PATH" https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb && sudo apt install -y "$DEB_PATH"
rm -f "$DEB_PATH"

# Prevent "Unlock Login Keyring" dialog on systems where the GNOME keyring
# is not auto-unlocked (e.g., auto-login or lightweight display managers).
DESKTOP_FILE=""
for candidate in \
    /usr/share/applications/google-chrome-stable.desktop \
    /usr/share/applications/google-chrome.desktop \
    "$HOME/.local/share/applications/google-chrome-stable.desktop" \
    "$HOME/.local/share/applications/google-chrome.desktop"; do
    if [ -f "$candidate" ]; then
        DESKTOP_FILE="$candidate"
        break
    fi
done

if [ -n "$DESKTOP_FILE" ]; then
    if ! grep -q '\-\-password-store=basic' "$DESKTOP_FILE"; then
        sudo sed -i 's|^Exec=\(.*\)|Exec=\1 --password-store=basic|' "$DESKTOP_FILE"
        echo "[*] Patched $DESKTOP_FILE to use --password-store=basic."
    else
        echo "[*] $DESKTOP_FILE already contains --password-store=basic, skipping patch."
    fi
else
    echo "[!] Warning: No Chrome .desktop file found. Keyring patch not applied."
fi
"""]

    commands.execute_bash_script_string(script_lines)

    return 0