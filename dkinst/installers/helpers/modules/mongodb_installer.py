import os
import sys
import requests
from typing import Union
import argparse
import subprocess
import urllib.request
from urllib.error import URLError, HTTPError
from typing import Literal

from rich.console import Console

from atomicshop import urls, web
from atomicshop.wrappers import ubuntu_terminal
from atomicshop.permissions import ubuntu_permissions

if os.name == 'nt':
    from atomicshop import get_process_list

from ..infra import system, msis, permissions


console = Console()


VERSION: str = "1.0.0"


def get_latest_mongodb_download_url(
        platform: Literal['windows', 'ubuntu'],
        rc_version: bool = False,
        major_specific: int = None
):
    if platform not in ['windows', 'ubuntu']:
        raise ValueError("Platform must be either 'windows' or 'ubuntu'.")

    response = requests.get(MONGODB_DOWNLOAD_PAGE_URL)

    if response.status_code != 200:
        raise MongoDBWebPageNoSuccessCodeError("Failed to load the download page.")

    urls_in_page: list = urls.find_urls_in_text(response.text)
    if not urls_in_page:
        raise MongoDBNoDownloadLinksError("Could not find the download link for MongoDB Community Server.")

    if platform == 'ubuntu':
        ubuntu_version: str = system.get_ubuntu_version().replace('.', '')
    else:
        ubuntu_version: str = ''

    found_urls: list = []
    for url in urls_in_page:
        if platform == 'windows':
            if 'windows' in url and 'x86_64' in url and url.endswith('.msi'):
                if not rc_version and '-rc' in url:
                    continue
                found_urls.append(url)
        elif platform == 'ubuntu':
            if 'ubuntu' in url and 'x86_64' in url and ubuntu_version in url and url.endswith('.tgz'):
                if '-rc' in url:
                    continue
                found_urls.append(url)

    if major_specific:
        version: str = str(major_specific)
        # If there is a dot at the end, remove it.
        if version.endswith("."):
            version = version[:-1]

        for url in found_urls:
            if f'-{version}.' in url:
                found_urls = [url]
                break

    if not found_urls:
        raise MongoDBNoDownloadLinkForWindowsError(
            "Could not find the download link for MongoDB Community Server for Windows x86_64.")

    # Return the latest URL only.
    return found_urls[0]


# === MONGODB WINDOWS INSTALLER ========================================================================================
MONGODB_DOWNLOAD_PAGE_URL: str = 'https://www.mongodb.com/try/download/community'
COMPASS_WIN_INSTALLATION_SCRIPT_URL: str = \
    'https://raw.githubusercontent.com/mongodb/mongo/master/src/mongo/installer/compass/Install-Compass.ps1'

WHERE_TO_SEARCH_FOR_MONGODB_EXE: str = 'C:\\Program Files\\MongoDB\\Server\\'
MONGODB_EXE_NAME: str = 'mongod.exe'


class MongoDBWebPageNoSuccessCodeError(Exception):
    pass


class MongoDBNoDownloadLinksError(Exception):
    pass


class MongoDBNoDownloadLinkForWindowsError(Exception):
    pass


class MongoDBInstallationError(Exception):
    pass


def is_service_running() -> bool:
    """
    Check if the MongoDB service is running.
    :return: bool, True if the MongoDB service is running, False otherwise.
    """

    if os.name == 'nt':
        current_processes: dict = (
            get_process_list.GetProcessList(get_method='pywin32', connect_on_init=True).get_processes())

        for pid, process_info in current_processes.items():
            if MONGODB_EXE_NAME in process_info['name']:
                return True
    else:
        raise NotImplementedError("This function is not implemented for this OS.")

    return False


def is_installed() -> Union[str, None]:
    """
    Check if MongoDB is installed.
    :return: string if MongoDB executable is found, None otherwise.
    """

    return system.find_file(MONGODB_EXE_NAME, WHERE_TO_SEARCH_FOR_MONGODB_EXE)


def install_mongodb_win(
        latest: bool = False,
        rc: bool = False,
        major: str = None,
        compass: bool = False,
        force: bool = False
) -> int:
    """
    Download and install the latest version of MongoDB Community Server on Windows.

    :param latest: bool, if True, the latest non-RC version will be downloaded.
    :param rc: bool, if True, the latest RC version will be downloaded.
    :param major: str, if set, the latest version of the specified major version will be downloaded.
    :param compass: bool, if True, MongoDB Compass will be installed.
    :param force: bool, if True, MongoDB will be installed even if it is already installed.
    :return: int, 0 if successful, 1 if failed.
    """

    if rc and latest:
        console.print("Both 'rc' and 'latest' cannot be True at the same time.", style='red')
        return 1

    if not (rc or latest) and not compass:
        console.print("At least one of 'rc', 'latest', or 'compass' must be True.", style='red')
        return 1

    # If we need to install mongo db.
    if rc or latest:
        if rc:
            download_rc_version: bool = True
        elif latest:
            download_rc_version: bool = False
        else:
            raise ValueError("Invalid value for 'rc' and 'latest'.")

        if is_service_running():
            console.print("MongoDB service is running - already installed. Use [-f] to reinstall.", style='blue', markup=False)

            if not force:
                return 0
        else:
            print("MongoDB is service is not running.")

            mongo_is_installed: Union[str, None] = is_installed()
            if is_installed():
                message = f"MongoDB is installed in: {mongo_is_installed}\n" \
                          f"The service is not running. Fix the service or use the 'force' parameter to reinstall."
                console.print(message, style='yellow')

                if not force:
                    return 0

        print("Fetching the latest MongoDB download URL...")
        mongo_installer_url = get_latest_mongodb_download_url(
            platform='windows', rc_version=download_rc_version, major_specific=major)

        print(f"Downloading MongoDB installer from: {mongo_installer_url}")
        installer_file_path: str = web.download(mongo_installer_url)

        print("Installing MongoDB...")
        try:
            msis.install_msi(
                installer_file_path,
                silent_no_gui=True,
                no_restart=True,
                terminate_required_processes=True,
                create_log_near_msi=True,
                scan_log_for_errors=True,
                additional_args='ADDLOCAL="ServerService"'
            )
        except msis.MsiInstallationError as e:
            console.print(f'{e} Exiting...', style='red')
            return 1

        # Check if MongoDB is installed.
        message: str = ''
        mongo_is_installed = is_installed()
        if not mongo_is_installed:
            message += "MongoDB Executable not found.\n"

        if not is_service_running():
            message += "MongoDB service is not running.\n"

        if message:
            message += f"MSI Path: {installer_file_path}"
            console.print(message, style='red')
            return 1
        else:
            success_message: str = f"MongoDB installed successfully to: {mongo_is_installed}\n" \
                                   f"Service is running."
            console.print(success_message, style='green')

        # Clean up the installer file
        if os.path.exists(installer_file_path):
            os.remove(installer_file_path)
            print("Cleaned up the installer file.")

    if not compass:
        return 0

    # It doesn't matter what you do with the MSI it will not install Compass, only if you run it manually.
    # So we will use installation script from their GitHub.
    print("Downloading MongoDB Compass installation script...")
    compass_script_path: str = web.download(COMPASS_WIN_INSTALLATION_SCRIPT_URL)

    print("Installing MongoDB Compass from script...")
    subprocess.run(["powershell", "-ExecutionPolicy", "Bypass", "-File", compass_script_path])

    # Clean up the installer file
    if os.path.exists(compass_script_path):
        os.remove(compass_script_path)
        print("Cleaned up the Compass installer file.")

    return 0
# === EOF MONGODB WINDOWS INSTALLER ====================================================================================


# === MONGODB UBUNTU INSTALLER =========================================================================================
COMPASS_UBUNTU_INSTALLATION_SCRIPT_URL: str = \
    'https://raw.githubusercontent.com/mongodb/mongo/master/src/mongo/installer/compass/install_compass'


def run_command(command):
    """Run a system command and exit if the command fails."""
    try:
        subprocess.run(command, check=True, shell=True)
        return 0
    except subprocess.CalledProcessError as e:
        console.print(f"Error: {e}", style='red')
        return 1


def _http_ok(url: str, timeout: int = 6) -> bool:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "python-urllib"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return 200 <= getattr(resp, "status", 0) < 300
    except (HTTPError, URLError, TimeoutError, Exception):
        return False

def _detect_latest_major_for_ubuntu(
        distro_codename: str,
        major: str = None
) -> str | None:
    """
    Find the newest MongoDB major that has:
      1) an APT Release file for this Ubuntu codename, and
      2) a matching PGP key file.
    Returns e.g. '8.0'.
    """
    # for m in range(max_major, min_major - 1, -1):
    download_url: str = get_latest_mongodb_download_url(platform='ubuntu', major_specific=major)
    ubuntu_version: str = system.get_ubuntu_version().replace('.', '')
    _, version_with_suffix = download_url.split(f'ubuntu{ubuntu_version}-')
    version: str = version_with_suffix.rsplit('.', 2)[0]

    release_url: str = (
        f"https://repo.mongodb.org/apt/ubuntu/dists/"
        f"{distro_codename}/mongodb-org/{version}/Release"
    )

    # For key url, even if the minor is 2, like 8.2, the key is still for 8.0
    major_only: str = version.split('.')[0]
    key_url: str = f"https://pgp.mongodb.com/server-{major_only}.0.asc"

    if _http_ok(release_url) and _http_ok(key_url):
        return version
    else:
        return None


def add_repo_and_install(
        latest: bool = True,
        major: str = None
) -> int:
    """Install the specified major version of MongoDB on Ubuntu."""

    if not latest and not major:
        console.print("Either 'latest' or 'major' must be specified.", style='red')
        return 1
    if latest and major:
        console.print("Only one of 'latest' or 'major' can be specified.", style='red')
        return 1

    distro_version = subprocess.check_output("lsb_release -sc", shell=True).decode('utf-8').strip()

    if latest:
        try:
            version: str = _detect_latest_major_for_ubuntu(distro_version, major)
        except Exception as e:
            console.print(f"Error detecting latest MongoDB version: {e}", style="red")
            return 1
    elif major:
        version: str = major
    else:
        raise ValueError("Invalid value for 'latest' and 'major'.")

    print(f"Installing MongoDB {version} on Ubuntu...")
    print(f"Installing Prerequisites...")
    ubuntu_terminal.update_system_packages()
    ubuntu_terminal.install_packages(["wget", "curl", "gnupg"])

    # We need the major version only for the key file. Since the key file will still need 8.0 even if the release is 8.2.
    major: str = version.split('.')[0]

    # Step 1: Import the MongoDB public GPG key
    print("Step 1: Importing the MongoDB public GPG key...")
    run_result: int = run_command(f"curl -fsSL https://pgp.mongodb.com/server-{major}.0.asc | "
                f"sudo gpg --dearmor --yes -o /usr/share/keyrings/mongodb-server-{major}.0.gpg")
    if run_result != 0:
        return run_result

    # Step 2: Create the MongoDB list file for APT
    print("Step 2: Creating MongoDB APT list file...")
    run_result: int = run_command(
        f"echo 'deb [ arch=amd64,arm64 signed-by=/usr/share/keyrings/mongodb-server-{major}.0.gpg ] "
        f"https://repo.mongodb.org/apt/ubuntu {distro_version}/mongodb-org/{version} multiverse' | "
        f"sudo tee /etc/apt/sources.list.d/mongodb-org-{version}.list")
    if run_result != 0:
        return run_result

    # Step 3: Update the APT package index
    print("Step 3: Updating the APT package index...")
    ubuntu_terminal.update_system_packages()

    # Step 4: Install the latest version of MongoDB for the specified major version
    print(f"Step 4: Installing MongoDB version {version}...")
    ubuntu_terminal.install_packages(["mongodb-org"])

    # Step 5: Start MongoDB service and enable it on startup
    print("Step 5: Starting MongoDB service and enabling it on startup...")
    result_code: int = ubuntu_terminal.start_enable_service_check_availability("mongod")
    if result_code != 0:
        return result_code

    console.print(f"MongoDB {version} installation complete!", style='green')
    return 0


def install_mongodb_ubuntu(
        latest: bool = False,
        major: str = None,
        compass: bool = False
) -> int:
    """
    Download and install the latest version of MongoDB Community Server on Ubuntu.

    :param latest: bool, if True, the latest non-RC version will be downloaded.
    :param major: str, Install the latest minor version of MongoDB Community Server on Ubuntu by providing the major version.
    :param compass: bool, if True, MongoDB Compass will be installed.
    :return:
    """

    run_result: int = add_repo_and_install(latest, major)
    if run_result != 0:
        return run_result

    if not compass:
        return 0

    # It doesn't matter what you do with the MSI it will not install Compass, only if you run it manually.
    # So we will use installation script from their GitHub.
    print("Downloading MongoDB Compass installation script...")
    compass_script_path: str = web.download(COMPASS_UBUNTU_INSTALLATION_SCRIPT_URL)

    print("Installing MongoDB Compass from script...")
    ubuntu_permissions.set_executable(compass_script_path)
    run_result: int = run_command(f'sudo -E python3 {compass_script_path}')
    if run_result != 0:
        return run_result

    # Clean up the installer file
    if os.path.exists(compass_script_path):
        os.remove(compass_script_path)
        print("Cleaned up the Compass installer file.")

    return 0
# === EOF MONGODB UBUNTU INSTALLER =====================================================================================


def _make_parser():
    parser = argparse.ArgumentParser(description='Install MongoDB Community Server.')

    parser.add_argument(
        '-l', '--latest',
        action='store_true',
        help='Install the latest version (not release candidate).'
    )
    parser.add_argument(
        '-r', '--rc',
        action='store_true',
        help='Install the latest version of MongoDB release candidate.'
    )
    parser.add_argument(
        '-m', '--major',
        type=str,
        help='Install the latest version of the specified major version.'
    )

    parser.add_argument(
        '-c', '--compass',
        action='store_true',
        help='Install MongoDB Compass.'
    )
    parser.add_argument(
        '-f', '--force',
        action='store_true',
        help='Force the installation even if MongoDB is already installed.'
    )

    return parser


def main(
        latest: bool = True,
        rc: bool = False,
        major: str = None,
        compass: bool = False,
        force: bool = False
) -> int:
    """
    Download and install the latest version of MongoDB Community Server on Windows.

    :param latest: bool, if True, the latest non-RC version will be downloaded.
    :param rc: bool, if True, the latest RC version will be downloaded.
    :param major: str, if set, the latest version of the specified major version will be downloaded.
    :param compass: bool, if True, MongoDB Compass will be installed.
    :param force: bool, if True, MongoDB will be installed even if it is already installed.
    :return: int, 0 if successful, 1 if failed.
    """

    if latest + rc + (major is not None) > 1:
        console.print("Only one of the arguments can be set to True or provided: latest, rc, major.", style="red")
        return 1
    if not latest and not rc and major is None and not compass:
        console.print("At least one of the arguments must be set to True or provided: latest, rc, major, compass.", style="red")
        return 1

    current_platform: str = system.get_platform()

    # Needs for both Windows and Ubuntu to check for admin rights.
    if not permissions.is_admin():
        console.print("This action requires administrator privileges.", style='red')
        if current_platform == "debian":
            venv = os.environ.get('VIRTUAL_ENV', None)
            if venv:
                print(f'Try: sudo "{venv}/bin/dkinst" install mongodb')
        return 1

    if current_platform == "debian":
        if force:
            console.print("On Debian, [force] argument currently is not applicable.", style="yellow", markup=False)
        if rc:
            console.print("On Debian, only [major], [compass] and [latest] arguments is implemented; [rc] argument isn't available.", style="red", markup=False)
            return 1
        result_code: int = install_mongodb_ubuntu(latest, major, compass)
        if result_code != 0:
            return result_code
    elif current_platform == "windows":
        result_code: int = install_mongodb_win(latest, rc, major, compass, force)
        if result_code != 0:
            return result_code
    else:
        console.print(f"MongoDB installation on {current_platform} is not implemented yet.", style="red")
        return 1

    return 0


if __name__ == '__main__':
    exec_parser = _make_parser()
    args = exec_parser.parse_args()
    sys.exit(main(**vars(args)))