from pathlib import Path
from types import ModuleType
from typing import Literal

from rich.console import Console

from . import _base
from .helpers.infra import system


console = Console()


class XRDP(_base.BaseInstaller):
    def __init__(self):
        super().__init__(__file__)
        self.description: str = "xRDP Installer"
        self.version: str = "1.0.0"
        self.platforms: list = ["debian"]

    def install(
            self,
    ):
        return install_function()

    def _show_help(
            self,
            method: Literal["install", "uninstall", "upgrade"]
    ) -> None:
        if method == "install":
            method_help: str = (
                "This method installs xrdp, prerequisites and XFCE4 desktop environment from apt repo.\n"
            )
            print(method_help)
        else:
            raise ValueError(f"Unknown method '{method}'.")


def install_function():
    script_lines = [
        """

echo "[*] Updating package lists..."
sudo -E apt update

echo "[*] Installing xrdp and Xorg backend..."
# xorgxrdp is the display backend used by xrdp for Ubuntu/GNOME
sudo -E apt install -y xrdp

echo "[*] Ensuring xrdp can use system TLS certs..."
# Normally set by package install, but harmless if repeated
sudo usermod -aG ssl-cert xrdp || true

echo "[*] Enabling and starting xrdp service..."
# sudo systemctl start xrdp
sudo systemctl enable --now xrdp

echo "[*] Opening firewall (TCP 3389) if UFW is active..."
if command -v ufw >/dev/null 2>&1; then
  if sudo ufw status | grep -q "Status: active"; then
    sudo ufw allow 3389/tcp
  else
    echo "UFW is installed but not active; no rule added."
  fi
else
  echo "UFW not installed; skipping firewall step."
fi

echo "[*] Verifying service status..."
sudo systemctl --no-pager --full status xrdp | sed -n '1,8p' || true

echo "[*] Installing XFCE (non-interactive, minimal)..."
sudo -E apt-get install -yq --no-install-recommends xfce4 xfce4-goodies

echo "[*] Configuring xrdp to start XFCE..."
# Write for the user running this script
echo xfce4-session > "$HOME/.xsession"
# If script is run via sudo later, also write for the original user
# if [ -n "${SUDO_USER:-}" ] && [ "$SUDO_USER" != "root" ]; then
#   sudo -u "$SUDO_USER" bash -lc 'echo xfce4-session > "$HOME/.xsession"'
# fi

sudo systemctl restart xrdp
sudo systemctl daemon-reload

IPV4=$(hostname -I 2>/dev/null | awk '{print $1}')
echo
echo "RDP is enabled."
echo "   • Service  : xrdp (port 3389/TCP)"
echo "   • Address  : ${IPV4:-<your-server-ip>}"
echo
echo "You will need to log out of your current session and use a desktop environment compatible with xrdp."
"""]

    system.execute_bash_script_string(script_lines)

    return 0