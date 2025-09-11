import sys
from pathlib import Path
import os
import tempfile

from rich.console import Console

from atomicshop import process, virtualization

# from ..infra import permissions


console = Console()


VERSION: str = "1.0.0"


def is_wsl_installed():
    if not permissions.is_admin():
        console.print("This option requires elevation.", style='red')
        return False

    # Command to check the status of the WSL feature
    command = "Get-WindowsOptionalFeature -Online -FeatureName Microsoft-Windows-Subsystem-Linux"

    # Check if WSL is enabled
    if "Enabled" in process.run_powershell_command(command):
        return True
    else:
        return False


def get_installed_distros(
        verbose: bool = False
) -> list:
    """
    Get a list of installed WSL distros.

    :param verbose: bool, True to print the command output to the console, False - don't print.
    :return: list, list of installed WSL distros.
    """
    return process.execute_with_live_output("wsl --list --quiet", verbose=verbose)


def get_available_distros_to_install() -> list:
    """
    Get a list of available WSL distros to install.
    :return: list, list of available WSL distros to install.
    """
    return process.execute_with_live_output("wsl --list --online")


def is_ubuntu_installed(
        version: str = None
) -> bool:
    """
    Check if Ubuntu distro is installed on WSL.

    :param version: string, Ubuntu version to check for. None, will check for any version.
        Example: '24.04'
    :return: bool, True if Ubuntu is installed, False otherwise.
    """

    if not version:
        version = str()

    installed_distros_list = get_installed_distros(verbose=False)

    if f'Ubuntu-{version}' in installed_distros_list:
        return True
    elif 'Ubuntu' in installed_distros_list:
        # Command to get Ubuntu version
        command = f"wsl -d Ubuntu lsb_release -a"

        # Execute the command
        result = process.execute_with_live_output(command)

        is_version_installed: bool = False
        # Parse the output for the version number
        for line in result:
            if "Release" in line and version in line:
                is_version_installed = True
                break

        return is_version_installed
    else:
        return False


def set_wsl_default_version_2() -> int:
    """
    Set WSL version 2 as the default version.

    :return: int, return code of the process. 0 if successful, non-zero otherwise.
    """

    print("Setting WSL version 2 as default...")
    process.run_powershell_command("wsl --set-default-version 2")

    return 0


def install_wsl_as_feature(
        enable_virtual_machine_platform: bool = True,
        set_default_version_2: bool = False
) -> int:
    """
        Install WSL on Windows by enabling the WSL feature without distro.

        :param enable_virtual_machine_platform: bool, True to enable Virtual Machine Platform feature.
        :param set_default_version_2: bool, True to set WSL version 2 as default. This is not applicable in the latest versions.

        :return: int, return code of the installation process. 0 if successful, non-zero otherwise.
        """

    # Temp directory to store the downloaded Ubuntu package.
    temp_dir = tempfile.gettempdir()

    # Check for admin privileges
    if not permissions.is_admin():
        console.print("Script must be run as administrator", style='red')
        return 1

    # Check if WSL is already installed
    if is_wsl_installed():
        console.print("WSL is already installed", style='green')
    else:
        # Enable WSL
        print("Enabling Windows Subsystem for Linux...")
        process.run_powershell_command(
            "Enable-WindowsOptionalFeature -Online -FeatureName Microsoft-Windows-Subsystem-Linux -NoRestart")

        # # Check if the system needs a reboot
        # if "RestartNeeded : True" in process.run_powershell_command(
        #         "Enable-WindowsOptionalFeature -Online -FeatureName Microsoft-Windows-Subsystem-Linux"):
        #     print("Please restart your computer to complete the installation of WSL and rerun the script.")
        #     return 0

    # Enable Virtual Machine Platform is needed for WSL 2.
    if enable_virtual_machine_platform:
        # Check if Hyper-V is enabled
        if "Enabled" in process.run_powershell_command(
                "Get-WindowsOptionalFeature -Online -FeatureName Microsoft-Hyper-V"):
            print("Hyper-V is enabled")
        else:
            # Command to enable Virtual Machine Platform
            command = "Enable-WindowsOptionalFeature -Online -FeatureName Microsoft-Hyper-V -All -NoRestart"

            print("Enabling Virtual Machine Platform...")
            process.run_powershell_command(command)

    if set_default_version_2:
        set_wsl_default_version_2()

    # Check if Ubuntu is already installed. If so, exit with a message.
    if is_ubuntu_installed():
        console.print("Ubuntu is already installed", style='green')
        return 0

    # Before you install Ubuntu, you need to set the WSL to version 2.
    # You can do it after you install, but if so, you will need to set the Ubuntu to version 2 either.
    # Download and Install Ubuntu.
    # print("Installing Ubuntu for WSL...")
    # package_file_path: str = str(Path(temp_dir, "Ubuntu.appx"))
    # process.run_powershell_command(
    #     f"Invoke-WebRequest -Uri https://aka.ms/wslubuntu2204 -OutFile {package_file_path} -UseBasicParsing")
    # process.run_powershell_command(f"Add-AppxPackage {package_file_path}")

    # # Clean up the downloaded package file.
    # if os.path.exists(package_file_path):
    #     os.remove(package_file_path)
    #
    # print("Ubuntu installation is complete. You can now launch Ubuntu from the Start Menu.")
    print("Check how to install specific distro manually:")
    print("  https://learn.microsoft.com/en-us/windows/wsl/install-manual")
    print("Please restart your computer to complete the installation.")

    return 0


def install_wsl_default_method(
        distro: str = None
) -> int:
    """
        Install WSL and add Ubuntu image, using the default method.
        When using 'wsl --install' command, it will enable the WSL feature, download and install the latest Ubuntu image from Microsoft Store.
        If you want to install specific distro, you can specify it using the 'distro' parameter.

        :param distro: string, distro to install. Using 'None' will install the default distro, which is the latest Ubuntu.
            Example: Ubuntu-24.04.

        :return: int, return code of the installation process. 0 if successful, non-zero otherwise.
        """

    # Check for admin privileges
    if not permissions.is_admin():
        console.print("Script must be run as administrator", style='red')
        return 1

    # Check if virtualization is enabled.
    if not virtualization.is_enabled():
        console.print("Virtualization is not enabled in the bios. Please enable it and rerun the script.", style='red')
        return 1

    # Check if WSL and Ubuntu is already installed
    wsl_installed: bool = is_wsl_installed()
    ubuntu_installed: bool = is_ubuntu_installed()

    if wsl_installed and ubuntu_installed:
        console.print("WSL and Ubuntu are already installed", style='green')
        return 0
    elif wsl_installed and not ubuntu_installed:
        print("WSL is already installed, installing Ubuntu")
    elif not wsl_installed:
        print("WSL is not installed, installing WSL and Ubuntu")

    if distro:
        command = f"wsl --install -d {distro}"
    else:
        command = "wsl --install"

    process.execute_with_live_output(command, verbose=True)

    return 0


def _make_parser():
    import argparse
    parser = argparse.ArgumentParser(description="Install WSL and distro on Windows.")
    parser.add_argument(
        "-i", "--install", action="store_true",
        help="Use the latest default method of installing WSL and Ubuntu from Microsoft Store using 'wsl' command.\n"
             "If the command isn't available, use the '-if' option to install WSL as a feature.")
    parser.add_argument(
        "-if", "--install-feature", action="store_true",
        help="Install WSL as a feature, and enable Virtual Machine Platform.\n"
             "Check how to install specific distro manually:\n"
             "  https://learn.microsoft.com/en-us/windows/wsl/install-manual")
    parser.add_argument(
        "--is-installed-wsl", action="store_true",
        help="Check if WSL is installed.")
    parser.add_argument(
        "--is-installed-ubuntu", type=str, default=None,
        help="Check if the specified version of Ubuntu is installed. Empty quotes, check if any version of Ubuntu is installed.\n"
                'Example: --is-installed-ubuntu "24.04"\n'
                'Example: --is-installed-ubuntu ""')
    parser.add_argument(
        "--set-v2-default", action="store_true",
        help="Set WSL version 2 as default.")

    return parser


def main(
        install: bool = False,
        install_feature: bool = False,
        is_installed_wsl: bool = False,
        is_installed_ubuntu: str = None,
        set_v2_default: bool = False
) -> int:

    if (install + install_feature) > 1:
        print("You cannot more than 1 argument of [--install], [--install_feature] at the same time.")
        return 1

    if install:
        return install_wsl_default_method()
    elif install_feature:
        return install_wsl_as_feature()

    if is_installed_wsl:
        if is_wsl_installed():
            print("wsl: true")
        else:
            print("wsl: false")

    if is_installed_ubuntu is not None:
        if is_ubuntu_installed(version=is_installed_ubuntu):
            print(f'ubuntu: true')
        else:
            print(f'ubuntu: false')

    if set_v2_default:
        set_wsl_default_version_2()

    return 0

if __name__ == '__main__':
    exec_parser = _make_parser()
    args = exec_parser.parse_args()
    sys.exit(main(**vars(args)))