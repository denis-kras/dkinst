import sys
import subprocess
import requests
import argparse

from rich.console import Console

from atomicshop.wrappers import githubw

from ..infra import permissions, msis, system


console = Console()


VERSION: str = "1.0.0"
"""Initial"""


# === WINDOWS FUNCTIONS ================================================================================================
import os
import time
import tempfile

from atomicshop import web


WINDOWS_X64_SUFFIX: str = "x64.msi"


class NodeJSWindowsInstallerNoVersionsFound(Exception):
    pass


class NodeJSWindowsInstallerMoreThanOneVersionFound(Exception):
    pass


class NodeJSWindowsInstallerFailedToExtractFileNameFromString(Exception):
    pass


class NodeJSWindowsInstallerFailedToExtractVersionInString(Exception):
    pass


def is_nodejs_installed_win() -> bool:
    """
    Check if Node.js is installed by trying to run 'node -v'.
    """
    print("Checking if Node.js is installed...")
    try:
        try:
            node_version = subprocess.check_output(["node", "-v"], text=True)
        except FileNotFoundError:
            console.print(f"node.exe is not found.", style="red")
            raise

        node_version = node_version.replace("\n", "")
        console.print(f"node.exe is found. Version: {node_version}", style="green")

        try:
            npm_version = subprocess.check_output(["npm.cmd", "-v"], text=True).strip()
        except FileNotFoundError:
            console.print(f"npm.cmd is not found.", style="red")
            raise

        npm_version = npm_version.replace("\n", "")
        console.print(f"npm.cmd is found. Version: {npm_version}", style="green")
        print("Node.js is installed.")
        return True
    except FileNotFoundError:
        print("Node.js is not installed.")
        return False


def add_nodejs_to_session_path_win():
    """
    Add Node.js to the PATH for the current CMD session.
    This is needed if the installation was done in the same session where
    you want to use Node.js right after the installation without restarting the CMD session.
    """

    print("Adding Node.js to the PATH for the current session...")
    # Get the installation directory from the default Node.js install path
    program_files = os.environ.get("ProgramFiles", "C:\\Program Files")
    nodejs_path = os.path.join(program_files, "nodejs")

    if os.path.exists(nodejs_path):
        print(f"Node.js installation found at: {nodejs_path}")
        current_path = os.environ.get("PATH", "")
        if nodejs_path not in current_path:
            # Add Node.js to the PATH for the current process
            os.environ["PATH"] = f"{nodejs_path};{current_path}"
            print("Node.js has been added to the PATH for this session.")
        else:
            print("Node.js is already in the current session PATH.")
    else:
        print("Node.js installation directory not found.")


def get_latest_nodejs_version_win() -> str | None:
    """
    Fetch the latest Node.js version from the official Node.js website.
    """
    print("Fetching the latest Node.js version...")
    url = "https://nodejs.org/dist/latest/SHASUMS256.txt"

    response = requests.get(url, timeout=10)
    response.raise_for_status()
    # Parse the file for the Node.js version
    found_versions: list = []
    for line in response.text.splitlines():
        if line.endswith(WINDOWS_X64_SUFFIX):
            found_versions.append(line)

    if not found_versions:
        raise NodeJSWindowsInstallerNoVersionsFound("No Node.js versions found in [https://nodejs.org/dist/latest/SHASUMS256.txt]")
    elif len(found_versions) > 1:
        raise NodeJSWindowsInstallerMoreThanOneVersionFound(f"More than one Node.js version found:\n"
                                                            f"{'\n'.join(found_versions)}")

    try:
        file_name = found_versions[0].split("  ")[-1]
    except IndexError:
        raise NodeJSWindowsInstallerFailedToExtractFileNameFromString("Failed to extract the file name from the string.")

    try:
        version = file_name.replace("node-v", "").replace(f"-{WINDOWS_X64_SUFFIX}", "")
    except Exception:
        raise NodeJSWindowsInstallerFailedToExtractVersionInString("Failed to extract the version from the string.")

    print(f"Latest Node.js version: {version}")
    return version


def download_nodejs_installer_win(version):
    """
    Download the Node.js MSI installer for Windows.
    """

    version = f"v{version}"
    nodejs_base_url = f"https://nodejs.org/dist/{version}/"
    file_name = f"node-{version}-x64.msi"
    download_url = nodejs_base_url + file_name
    print(f"Downloading Node.js installer from: {download_url}")

    # Make temporary directory to store the installer
    temp_dir = tempfile.gettempdir()
    temp_file_path = web.download(download_url, temp_dir)
    return temp_file_path


def clean_up_win(installer_path) -> None:
    """
    Remove the installer file after installation.
    """

    if os.path.exists(installer_path):
        os.remove(installer_path)
        print(f"Removed installer: {installer_path}")


def install_nodejs_win(
        force: bool = False
) -> int:
    """
    Install Node.js on Windows.

    :param force: bool, if True, the function will install Node.js even if it is already installed.
    :return: int, 0 if successful, 1 if failed.
    """

    if not permissions.is_admin():
        console.print("This script requires administrative privileges to install Node.js.", style="red")
        return 1

    if is_nodejs_installed_win() and not force:
            console.print("Node.js is already installed. Use the [force] to install without prompt. Do you want to install anyway? [y/n]", style="yellow", markup=False)
            if input().strip().lower() != 'y':
                print("Exiting without installation.")
                return 0

    console.print("Starting Node.js installation process...", style="blue")
    try:
        version = get_latest_nodejs_version_win()
    except Exception as e:
        console.print(str(e), style="red")
        return 1
    if not version:
        console.print("Exiting: Could not fetch the latest Node.js version.", style="red")
        return 1

    installer_path = download_nodejs_installer_win(version)
    if not installer_path:
        console.print("Exiting: Failed to download the Node.js installer.", style="red")
        return 1

    msis.install_msi(installer_path, silent_progress_bar=True)
    time.sleep(5)  # Wait a few seconds for the installation to complete

    try:
        clean_up_win(installer_path)
    except Exception as e:
        console.print(f"Failed to clean up the installer: {e}", style="red")
        return 1
    console.print("Installation process finished.", style="green")

    # Add Node.js to the PATH for the current session, so we can verify the installation right away.
    add_nodejs_to_session_path_win()
    if not is_nodejs_installed_win():
        console.print("Node.js installation verification failed.", style="red")
        return 1

    return 0
# === EOF WINDOWS FUNCTIONS ============================================================================================


# === UBUNTU FUNCTIONS =================================================================================================
def install_npm_package_ubuntu(package_name: str, sudo: bool = True):
    """
    The function will install a npm package on Ubuntu.
    :param package_name: str, the name of the package to install.
    :param sudo: bool, if True, the function will use sudo.
        NPM commands require sudo to install global packages.
    :return:
    """

    # Check if Node.js is installed.
    if not is_nodejs_installed_ubuntu():
        return

    command = f"npm install -g {package_name}"

    if sudo:
        command = f"sudo {command}"

    _ = subprocess.check_output(command, shell=True, stderr=subprocess.STDOUT)


def is_nodejs_installed_ubuntu():
    """
    The function will check if Node.js is installed.
    :return: bool.
    """

    try:
        # Run the command 'node -v'
        result = subprocess.run(['node', '-v'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        # Check if the command was successful
        if result.returncode == 0:
            message = f"Node.js installed. Version: {result.stdout.strip()}"
            console.print(message, style='green')
            return True
        else:
            print("Node.js is not installed.")
            return False
    except FileNotFoundError:
        print("Node command not found. Node.js is not installed.")
        return False


def get_nodejs_latest_version_ubuntu(
        by_github_api: bool = True,
        _by_nodejs_website: bool = False,
        get_major: bool = False
) -> str:
    """
    The function will get the latest version number of Node.js.
    :param by_github_api: bool, if True, the function will get the version number using the GitHub API.
        Limitations: rate limits apply.
    :param _by_nodejs_website: bool, if True, the function will get the version number using the Node.js website.
        Limitations: the website structure can change and the json file is relatively large.
        This is only for reference, it is not tested.
    :param get_major: bool, if True, the function will return only the major version number string.
    :return: str.
    """

    if by_github_api and _by_nodejs_website:
        raise ValueError("Only one of the arguments can be True.")
    elif not by_github_api and not _by_nodejs_website:
        raise ValueError("At least one of the arguments must be True.")

    latest_version = ''
    if by_github_api:
        github_wrapper = githubw.GitHubWrapper('nodejs', 'node')
        latest_version = github_wrapper.get_latest_release_version()
    elif _by_nodejs_website:
        url = "https://nodejs.org/dist/index.json"
        response = requests.get(url)
        versions = response.json()
        latest_version = versions[0]['version']  # Assuming the first one is the latest.

    if get_major:
        latest_version = latest_version.replace('v', '')
        latest_version = latest_version.split('.')[0]

    return latest_version


def install_nodejs_ubuntu(
        latest: bool = False,
        lts: bool = True,
        version: str = None,
        force: bool = False
):
    """
    The function will install Node.js on Ubuntu.

    :param latest: bool, if True, the function will install the latest version of Node.js.
    :param lts: bool, if True, the function will install the LTS version of Node.js.
    :param version: str, the version number of Node.js to install.
    :param force: bool, if True, the function will install Node.js even if it is already installed.

    :return:
    """

    if latest + lts + (version is not None) > 1:
        raise ValueError("Only one of the arguments can be set to True or provided: latest, lts, version.")
    if not latest and not lts and version is None:
        raise ValueError("At least one of the arguments must be set to True or provided: latest, lts, version.")

    # Check if Node.js is already installed.
    if is_nodejs_installed_ubuntu():
        if not force:
            return

    # NodeSource is listed as source under official Node.js GitHub repository:
    # https://github.com/nodejs/node?tab=readme-ov-file#current-and-lts-releases
    print("Adding NodeSource repository...")

    # Fetch and execute the NodeSource repository setup script.
    if latest:
        version: str = get_nodejs_latest_version_ubuntu(get_major=True)

    command: str = ''
    if latest or version:
        command = f"curl -fsSL https://deb.nodesource.com/setup_{version}.x | sudo -E bash -"
    elif lts:
        command = "curl -fsSL https://deb.nodesource.com/setup_current.x | sudo -E bash -"

    _ = subprocess.check_output(command, shell=True, stderr=subprocess.STDOUT)

    subprocess.check_call(['sudo', 'apt', 'update'])
    subprocess.check_call(["sudo", "apt", "install", "-y", "nodejs"])

    # Check if Node.js is installed.
    is_nodejs_installed_ubuntu()
# === EOF UBUNTU FUNCTIONS =============================================================================================


def _make_parser():
    parser = argparse.ArgumentParser(description="Install Node.js on Ubuntu.")
    parser.add_argument(
        '--latest',
        action='store_true',
        help="Install the latest version of Node.js."
    )
    parser.add_argument(
        '--lts',
        action='store_true',
        help="Install the LTS version of Node.js. Available only for Ubuntu."
    )
    parser.add_argument(
        '--version',
        type=str,
        help="Install a specific version of Node.js. Available only for Ubuntu."
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help="Force the installation of Node.js."
    )

    return parser


def main(
        latest: bool = False,
        lts: bool = False,
        version: str = None,
        force: bool = False
) -> int:
    """
    The function will install Node.js on Ubuntu or Windows.

    :param latest: bool, if True, the function will install the latest version of Node.js.
    :param lts: bool, if True, the function will install the LTS version of Node.js.
    :param version: str, the version number of Node.js to install.
    :param force: bool, if True, the function will install Node.js even if it is already installed.

    :return:
    """

    if latest + lts + (version is not None) > 1:
        raise ValueError("Only one of the arguments can be set to True or provided: latest, lts, version.")
    if not latest and not lts and version is None:
        raise ValueError("At least one of the arguments must be set to True or provided: latest, lts, version.")

    current_platform: str = system.get_platform()
    if current_platform == "debian":
        install_nodejs_ubuntu(latest, lts, version, force)
    elif current_platform == "windows":
        if version or lts:
            console.print("On Windows, only [latest] arguments is implemented; [version] and [lts] arguments aren't available.", style="red", markup=False)
            return 1
        install_nodejs_win(force)
    else:
        console.print(f"Node.js installation on {current_platform} is not implemented yet.", style="red")
        return 1

    return 0


if __name__ == '__main__':
    nodejs_parser = _make_parser()
    args = nodejs_parser.parse_args()
    sys.exit(main(**vars(args)))