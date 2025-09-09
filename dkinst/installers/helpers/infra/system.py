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


def find_file(
        file_name: str,
        directory_path: str
):
    """
    The function finds the file in the directory recursively.
    :param file_name: string, The name of the file to find.
    :param directory_path: string, The directory to search in.
    :return:
    """
    for dir_path, dir_names, filenames in os.walk(directory_path):
        for filename in filenames:
            if filename == file_name:
                return os.path.join(dir_path, filename)
    return None