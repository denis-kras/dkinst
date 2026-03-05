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


def get_ubuntu_version() -> str | None:
    """Return the Ubuntu version as a string, or None if not on Ubuntu."""
    if os.path.exists("/etc/os-release"):
        with open("/etc/os-release") as f:
            data = f.read().lower()
            if "ubuntu" in data:
                for line in data.splitlines():
                    if line.startswith("version_id="):
                        return line.split("=")[1].strip().strip('"')
    return None


def get_architecture() -> str:
    """Return the system architecture as a string."""
    arch = platform.machine().lower()
    if arch in ["x86_64", "amd64"]:
        return "x64"
    elif arch in ["i386", "i486", "i586", "i686", "i786", "x86"]:
        return "x86"
    elif arch in ["aarch64", "arm64"]:
        return "arm64"
    elif arch in ["armv7l", "armv8l", "arm", "aarch32"]:
        return "arm"
    else:
        raise ValueError(f"Unknown architecture: {arch}")
