import os
import platform


def get_platform() -> str:
    """Return the current platform as a string."""
    current_platform = platform.system().lower()
    if current_platform == "windows":
        return "windows"
    elif current_platform == "linux":
        if is_debian():
            return "debian"
        else:
            return "linux unknown"
    else:
        return ""


def is_debian() -> bool:
    """Check if the current Linux distribution is Debian-based."""
    if os.path.exists("/etc/os-release"):
        with open("/etc/os-release") as f:
            data = f.read().lower()
            return "debian" in data
    return False