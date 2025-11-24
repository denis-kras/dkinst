from pathlib import Path
from types import ModuleType
from typing import Literal
import subprocess
import os
import tempfile
import shutil
import shlex

from atomicshop.wrappers.githubw import GitHubWrapper

from . import _base
from .helpers.infra import system
from .helpers.infra.printing import printc


GIT_REPO_URL: str = "https://github.com/Vishram1123/gjs-osk"
UUID: str = "gjsosk@vishram1123.com"


class VirtualKeyboard(_base.BaseInstaller):
    def __init__(self):
        super().__init__()
        self.version: str = "1.0.1"
        # Changed from direct dbus to GitHub file install.

        self.name: str = Path(__file__).stem
        self.description: str = "Virtual Keyboard GJS OSK Installer"
        self.platforms: list = ["debian"]
        self.helper: ModuleType | None = None

    def install(
            self,
    ):
        return install_function()

    def _show_help(
            self,
            method: Literal["install", "uninstall", "update"]
    ) -> None:
        if method == "install":
            method_help: str = (
                "This method installs gnome-extensions from apt repo and then the GJS OSK extension (virtual keyboard).\n"
                "You will be prompted to click 'Install' in the GUI Extension Manager.\n"
            )
            print(method_help)
        else:
            raise ValueError(f"Unknown method '{method}'.")


def install_function():
    # Get Gnome version.
    gnome_version: str = subprocess.check_output(
        ["gnome-shell", "--version"],
        text=True
    ).strip().split(" ")[2]
    print(f"Detected Gnome version: {gnome_version}")

    if is_extension_installed(UUID) and is_extension_enabled(UUID):
        printc("GJS OSK extension is already installed and enabled.", color="yellow")
        return 0
    elif is_extension_installed(UUID) and not is_extension_enabled(UUID):
        printc("GJS OSK extension is already installed but not enabled. Enabling now...", color="yellow")
        system.execute_bash_script_string([
            f"gnome-extensions enable {UUID} || true"
        ])
        printc("GJS OSK extension has been enabled.", color="green")
        return 0

    if int(gnome_version.split(".")[0]) > 45:
        channel: str = "main"
    else:
        channel = "pre-45"

    with tempfile.TemporaryDirectory() as tmpdir:
        temp_dir: str = str(Path(tmpdir))
    os.makedirs(temp_dir, exist_ok=True)

    github_wrapper: GitHubWrapper = GitHubWrapper(
        repo_url=GIT_REPO_URL
    )

    downloaded_release_path: str = github_wrapper.download_latest_release(
        target_directory=temp_dir,
        asset_pattern=f"*{channel}*"
    )

    script_lines = [
        f"""

if [[ "${{XDG_SESSION_TYPE:-}}" != "wayland" ]]; then
  echo "NOTE: GJS OSK works best on Wayland (X11 is not supported well)."
fi

sudo apt update
sudo apt install -y gnome-shell-extension-manager curl

gnome-extensions install --force "{downloaded_release_path}"
# gnome-extensions enable "$UUID" || true

# This command can be used to install directly, but with GUI prompt for confirmation.
# gdbus call --session --dest org.gnome.Shell.Extensions --object-path /org/gnome/Shell/Extensions --method org.gnome.Shell.Extensions.InstallRemoteExtension "{UUID}"

# --- (Optional) Disable built-in GNOME OSK to avoid conflicts ---------------
# Comment out the next line if you want to keep GNOME's default OSK enabled.
# gsettings set org.gnome.desktop.a11y.applications screen-keyboard-enabled false || true
"""]

    system.execute_bash_script_string(script_lines)

    # Cleanup
    shutil.rmtree(temp_dir)

    printc("Installation complete. Please LOG OUT/LOG IN to apply changes.\n"
                  "You can enable it manually or run [dkinst install virtual_keyboard] again to enable.", color="green")

    return 0


def _bash_ok(cmd: str) -> bool:
    """Run a bash command and return True on exit code 0, else False."""
    proc = subprocess.run(
        ["bash", "-lc", cmd],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return proc.returncode == 0


def is_extension_installed(uuid: str = UUID) -> bool:
    """True if the UUID appears in `gnome-extensions list`."""
    return _bash_ok(f"gnome-extensions list | grep -Fxq {shlex.quote(uuid)}")


def is_extension_enabled(uuid: str = UUID) -> bool:
    """True if the UUID appears in `gnome-extensions list --enabled`."""
    return _bash_ok(f"gnome-extensions list --enabled | grep -Fxq {shlex.quote(uuid)}")