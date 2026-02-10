import os
import subprocess
import shutil
import time


def is_executable_exists(package: str) -> bool:
    """
    Function checks if a package is installed.
    :param package: str, package name.
    :return:
    """

    if not shutil.which(package):
        return False
    else:
        return True


def update_system_packages():
    """
    Function updates the system packages.
    :return:
    """
    subprocess.check_call(['sudo', 'apt', 'update'])


def install_packages(
        package_list: list[str],
        timeout_seconds: int = 0,
):
    """
    Function installs a package using apt-get.
    :param package_list: list of strings, package names to install.
    :param timeout_seconds: int, if the 'apt-get' command is busy at the moment, the function will wait for
        'timeout_seconds' seconds before raising an error.
        '-1' means wait indefinitely.
    :return:
    """

    # Construct the command with the package list
    command = ["sudo", "apt", "install", "-y"] + package_list

    if timeout_seconds != 0:
        command.extend(["-o", f"DPkg::Lock::Timeout={str(timeout_seconds)}"])

    subprocess.check_call(command)


def is_package_installed(package: str) -> bool:
    """
    Function checks if a package is installed.
    :param package: str, package name.
    :return:
    """

    try:
        # Run the dpkg-query command to check if the package is installed
        result = subprocess.run(
            ['apt', '-qq', 'list', '--installed', package], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        # If the return code is 0 and the output contains 'install ok installed', the package is installed
        if result.returncode == 0 and result.stdout != b'':
            return True
        else:
            return False
    except Exception as e:
        print(f"An error occurred: {e}")
        return False


def get_command_execution_as_sudo_executer(command: str, add_bash_exec: bool = False) -> str:
    """
    Function gets the command execution as the sudo executer.
    The input command should be without 'sudo', if it will be, it will be omitted.
    :param command: str, the command to execute.
    :param add_bash_exec: bool, if True, the command will be executed with bash.
        Example command: 'systemctl --user start docker.service'
        Example command with add_bash_exec: 'su <sudo_executioner_user> -c "/bin/bash systemctl --user start docker.service"'
        Example command without add_bash_exec: 'su <sudo_executioner_user> -c "systemctl --user start docker.service"'
    :return: str, the command execution as the sudo executer.
    """

    if command.startswith('sudo'):
        if command.startswith('sudo -'):
            raise ValueError("The command should not start with 'sudo -'.")

        command = command.replace('sudo ', '').strip()

    sudo_executer_username: str = ubuntu_permissions.get_sudo_executer_username()

    if sudo_executer_username:
        if add_bash_exec:
            command = f'/bin/bash {command}'
        return f'su {sudo_executer_username} -c "{command}"'
    else:
        return command


def add_path_to_bashrc(as_regular_user: bool = False):
    """Add $HOME/bin to the PATH in .bashrc if it's not already present.
    :param as_regular_user: bool, if True, the function will run as a regular user even if executed with sudo.
    """
    home_path_bashrc = "~/.bashrc"

    if as_regular_user:
        # Get the current non-sudo user
        with ubuntu_permissions.temporary_regular_permissions():
            current_non_sudo_user = os.getlogin()

        # Get the home path of the current non-sudo user
        user_bashrc_path = ubuntu_permissions.expand_user_path(current_non_sudo_user, home_path_bashrc)
    else:
        user_bashrc_path = os.path.expanduser(home_path_bashrc)

    new_path = 'export PATH=$PATH:$HOME/bin\n'
    with open(user_bashrc_path, 'r+') as bashrc:
        content = bashrc.read()
        if "$HOME/bin" not in content:
            bashrc.write(new_path)
            print("Added $HOME/bin to .bashrc")
        else:
            print("$HOME/bin already in .bashrc")


def start_enable_service_check_availability(
        service_name: str,
        wait_time_seconds: float = 30,
        start_service_bool: bool = True,
        enable_service_bool: bool = True,
        check_service_running: bool = True,
        user_mode: bool = False,
        sudo: bool = True
) -> int:
    """
    Function starts and enables a service and checks its availability.

    :param service_name: str, the service name.
    :param wait_time_seconds: float, the time to wait after starting the service before checking the service
        availability.
    :param start_service_bool: bool, if True, the service will be started.
    :param enable_service_bool: bool, if True, the service will be enabled.
    :param check_service_running: bool, if True, the function will check if the service is running.
    :param user_mode: bool, if True, the service will be started and enabled in user mode.
    :param sudo: bool, if True, the command will be executed with sudo.

    :return: int, 0 if the service is running, 1 if the service is not running.
    """

    if not start_service_bool and not enable_service_bool:
        raise ValueError("Either 'start_service_bool' or 'enable_service_bool' must be True.")

    # Start and enable the service.
    if start_service_bool:
        start_service(service_name, user_mode=user_mode, sudo=sudo)
    if enable_service_bool:
        enable_service(service_name, user_mode=user_mode,sudo=sudo)

    if check_service_running:
        print(f"Waiting up to {str(wait_time_seconds)} seconds for the program to start.")
        count: int = 0
        while not is_service_running(service_name, user_mode=user_mode) and count < wait_time_seconds:
            count += 1
            time.sleep(1)

        if not is_service_running(service_name, user_mode=user_mode):
            console.print(f"[{service_name}] service failed to start.", style='red', markup=False)
            return 1
        else:
            console.print(f"[{service_name}] service is running.", style='green', markup=False)

    return 0