import sys
import os
import argparse
import requests
from bs4 import BeautifulSoup
import subprocess

from rich.console import Console

from atomicshop import process, web

from ..infra import system


console = Console()


VERSION: str = "1.0.0"


# === WINDOWS FUNCTIONS ================================================================================================
def install_win():
    """
    Main function to download and install the latest PyCharm Community Edition.

    Usage:
    python -m atomicshop.mains.installs.pycharm

    Or run the main function directly.
        from atomicshop.wrappers import pycharmw


        def main():
            pycharmw.download_install_main()


        if __name__ == "__main__":
            main()
    """

    def get_latest_pycharm_download_link():
        url = "https://www.jetbrains.com/pycharm/download/"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }

        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            raise Exception("Failed to load the download page")

        soup = BeautifulSoup(response.text, 'html.parser')
        download_link = None

        # Find the Professional version download link
        for a in soup.find_all('a', href=True):
            if '/download?code=PCC&platform=windows' in a['href']:
                download_link = a['href']
                break

        if not download_link:
            raise Exception("Could not find the download link for the latest version of PyCharm Professional")

        return f"https:{download_link}"

    installer_path: str | None = None
    try:
        print("Fetching the latest PyCharm download link...")
        download_url = get_latest_pycharm_download_link()
        print(f"Download URL: {download_url}")

        print("Starting the download...")
        file_name = "pycharm-latest.exe"
        # download_file(download_url, file_name)
        installer_path = web.download(file_url=download_url, file_name=file_name, use_certifi_ca_repository=True)
        console.print(f"Downloaded the latest version of PyCharm to: {file_name}", style='green')
    except Exception as e:
        print(f"An error occurred: {e}")

    if not installer_path:
        console.print("Failed to download the latest version of PyCharm", style='red')
        return 1

    # Install PyCharm
    # Run the installer
    print("Running the installer...")
    subprocess.run([installer_path, '/S'], check=True)  # /S for silent installation
    console.print("Installation complete.", style='green')

    # Remove the installer
    os.remove(installer_path)
# === EOF WINDOWS FUNCTIONS ============================================================================================


# === UBUNTU FUNCTIONS =================================================================================================
def install_ubuntu(enable_sudo_execution: bool = False) -> int:
    """
    Main function to install the latest PyCharm unified Edition.
    """

    process.execute_script('sudo snap install pycharm-professional --classic', shell=True)

    if enable_sudo_execution:
        process.execute_script('xhost +SI:localuser:root', shell=True)
        console.print('Run the following command to start PyCharm as root: [sudo snap run pycharm-professional]', style='blue', markup=False)
    return 0
# === EOF UBUNTU FUNCTIONS =============================================================================================


def _make_parser():
    """
    Parse command line arguments.

    :return: Parsed arguments.
    """
    parser = argparse.ArgumentParser(description='Install PyCharm Community Edition.')
    parser.add_argument(
        '--enable_sudo_execution', action='store_true',
        help='There is a problem when trying to run snapd installed Pycharm as sudo, need to enable this.'
             'This is not a good security practice to run GUI apps as root. Only if you know what you doing.')

    return parser


def main(
        enable_sudo_execution: bool = False
) -> int:
    """
    The function will install Node.js on Ubuntu or Windows.

    :param enable_sudo_execution: bool: Enable sudo execution for snapd installed PyCharm.

    :return: int: 0 if success, 1 if error.
    """

    current_platform: str = system.get_platform()
    if current_platform == "debian":
        install_ubuntu(enable_sudo_execution)
    elif current_platform == "windows":
        install_win()
    else:
        console.print(f"PyCharm installation on {current_platform} is not implemented yet.", style="red")
        return 1

    return 0


if __name__ == '__main__':
    pycharm_parser = _make_parser()
    args = pycharm_parser.parse_args()
    sys.exit(main(**vars(args)))