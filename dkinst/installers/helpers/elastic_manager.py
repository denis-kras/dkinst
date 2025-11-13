import sys
import os
import argparse
import requests
import time

from rich.console import Console

from atomicshop.wrappers import ubuntu_terminal
from atomicshop import process

from .infra import permissions


console = Console()


VERSION: str = "1.0.0"


DEFAULT_ELASTIC_PORT: str = '9200'
DEFAULT_ELASTIC_HOST: str = 'localhost'
DEFAULT_ELASTIC_URL: str = f"http://{DEFAULT_ELASTIC_HOST}:{DEFAULT_ELASTIC_PORT}"
DEFAULT_ELASTIC_URL_JVM_OPTIONS: str = f"{DEFAULT_ELASTIC_URL}/_nodes?filter_path=**.jvm&pretty"

DEFAULT_KIBANA_PORT: str = '5601'
DEFAULT_KIBANA_HOST: str = 'localhost'
DEFAULT_KIBANA_URL: str = f"http://{DEFAULT_KIBANA_HOST}:{DEFAULT_KIBANA_PORT}"

UBUNTU_DEPENDENCY_PACKAGES: list[str] = ['apt-transport-https', 'openjdk-11-jdk', 'wget']
UBUNTU_ELASTIC_PACKAGE_SERVICE_NAME: str = 'elasticsearch'
UBUNTU_KIBANA_PACKAGE_SERVICE_NAME: str = 'kibana'

ELASTIC_SEARCH_CONFIG_DIRECTORY: str = "/etc/elasticsearch"

ELASTIC_CONFIG_FILE: str = f"{ELASTIC_SEARCH_CONFIG_DIRECTORY}/elasticsearch.yml"
XPACK_SECURITY_SETTING_NAME: str = "xpack.security.enabled"

ELASTIC_JVM_OPTIONS_DIRECTORY: str = f"{ELASTIC_SEARCH_CONFIG_DIRECTORY}/jvm.options.d"
ELASTIC_JVM_OPTIONS_4GB_CUSTOM_FILE: str = f"{ELASTIC_JVM_OPTIONS_DIRECTORY}/4gb_memory_heap.options"
ELASTIC_JVM_OPTIONS_4GB_MEMORY_USAGE: list[str] = ['-Xms4g', '-Xmx4g']


# This is pure bash script.
"""
#!/bin/bash

# Color text in red.
echo_red() {
    local color="\e[31m"  # Red color
    local reset="\e[0m"   # Reset formatting
    echo -e "${color}$1${reset}"
}

# Function to check if a service is running
check_service_running() {
    local service_name=$1
    local status=$(systemctl is-active "$service_name")

    if [ "$status" == "active" ]; then
        echo "$service_name service is active and running."
        return 0
    else
        echo_red "$service_name service is not running or has failed. Status: $service_status, Failed: $service_failed"
        return 1
    fi
}

# Update and upgrade system packages
sudo apt-get update && sudo apt-get upgrade -y

# Install necessary dependencies
sudo apt-get install apt-transport-https openjdk-11-jdk wget -y

# Download and install the GPG signing key
wget -qO - https://artifacts.elastic.co/GPG-KEY-elasticsearch | gpg --dearmor | sudo tee /usr/share/keyrings/elasticsearch-keyring.gpg > /dev/null

# Add the Elastic repository to the system
echo "deb [signed-by=/usr/share/keyrings/elasticsearch-keyring.gpg] https://artifacts.elastic.co/packages/8.x/apt stable main" | sudo tee /etc/apt/sources.list.d/elastic-8.x.list

# Update package index
sudo apt-get update

# Install Elasticsearch
sudo apt-get install elasticsearch -y

# Path to the Elasticsearch configuration file
CONFIG_FILE="/etc/elasticsearch/elasticsearch.yml"

# Check if the configuration file exists
if [ ! -f "$CONFIG_FILE" ]; then
    echo "Configuration file does not exist at $CONFIG_FILE."
    exit 1
fi

# Function to check the setting in the configuration file
check_setting() {
    if grep -q "^xpack.security.enabled: false" "$CONFIG_FILE"; then
        echo "The setting is confirmed to be 'xpack.security.enabled: false'."
    else
        echo "Failed to set 'xpack.security.enabled: false'."
        exit 1
    fi
}

# Check if 'xpack.security.enabled' is set to 'false'
if grep -q "^xpack.security.enabled: false" "$CONFIG_FILE"; then
    echo "The setting is already set to false."
elif grep -q "^xpack.security.enabled: true" "$CONFIG_FILE"; then
    # If the setting is true, change it to false
    sudo sed -i 's/^xpack.security.enabled: true/xpack.security.enabled: false/' "$CONFIG_FILE"
    echo "Changed xpack.security.enabled to false."
    check_setting
else
    # If the setting doesn't exist, add it
    echo "xpack.security.enabled: false" | sudo tee -a "$CONFIG_FILE" > /dev/null
    echo "Added xpack.security.enabled: false to the configuration."
    check_setting
fi

# Start and enable Elasticsearch service
sudo systemctl start elasticsearch
sudo systemctl enable elasticsearch

echo "Waiting 30 seconds for program to start before availability check..."
sleep 30

# Check if Elasticsearch service is running
if ! check_service_running "elasticsearch"; then
    echo "Elasticsearch service failed to start. Exiting."
    exit 1
fi

# Function to check if Elasticsearch is up and running
check_elasticsearch() {
    max_attempts=5
    wait_seconds=10

    for ((i=1; i<=max_attempts; i++)); do
        echo "Checking if Elasticsearch is running (Attempt $i/$max_attempts)..."

        # Using curl to get the HTTP status code
        status=$(curl --write-out %{http_code} --silent --output /dev/null http://localhost:9200)

        if [ "$status" -eq 200 ]; then
            echo "Elasticsearch is up and running."
            return 0
        else
            echo "Elasticsearch is not running. Status code: $status"
        fi

        echo "Waiting for Elasticsearch to start..."
        sleep $wait_seconds
    done

    echo "Elasticsearch did not start within the expected time."
    return 1
}

# Check if Elasticsearch is running
if ! check_elasticsearch; then
    echo "Elasticsearch failed to start. Exiting."
    exit 1
fi

# Install Kibana
sudo apt-get install kibana -y

# Start and enable Kibana service
sudo systemctl start kibana
sudo systemctl enable kibana

echo "Waiting 30 seconds for program to start before availability check..."
sleep 30

# Check if Kibana service is running
if ! check_service_running "kibana"; then
    echo "Kibana service failed to start. Exiting."
    exit 1
fi

# Print status
echo "Elasticsearch and Kibana installation completed."
echo "Elasticsearch is running on http://localhost:9200"
echo "Kibana is running on http://localhost:5601"
"""


def check_xpack_security_setting(config_file_path: str = None):
    """
    The function checks if the 'xpack.security.enabled' setting is set to 'false' in the Elasticsearch
    configuration file.

    :param config_file_path:
    :return:
    """

    if not config_file_path:
        config_file_path = ELASTIC_CONFIG_FILE

    with open(config_file_path, 'r') as file:
        # Read the file contents
        contents = file.read()
        # Check if the specific setting exists
        if f"{XPACK_SECURITY_SETTING_NAME}: false" in contents:
            return False
        elif f"{XPACK_SECURITY_SETTING_NAME}: true" in contents:
            return True
        # If the setting doesn't exist, return None.
        else:
            return None


def modify_xpack_security_setting(
        config_file_path: str = None,
        setting: bool = False,
        output_message: bool = True
) -> int:
    """
    The function modifies the 'xpack.security.enabled' setting in the Elasticsearch configuration file.
    :param config_file_path: str, the path to the configuration file.
    :param setting: bool, the setting to change to. Will be added, if doesn't exist.
    :param output_message: bool, if True, the function will print a message.
    :return: int, 0 if successful, 1 if an error occurred.
    """

    if not config_file_path:
        config_file_path = ELASTIC_CONFIG_FILE

    # Check if the configuration file exists.
    if not os.path.isfile(ELASTIC_CONFIG_FILE):
        console.print(f"Configuration file does not exist at: {ELASTIC_CONFIG_FILE}.", style='red')
        return 1

    # The setting to set in the configuration file.
    xpack_setting_to_set: str = f'{XPACK_SECURITY_SETTING_NAME}: {str(setting).lower()}'

    # Check if the setting exists in the configuration file and get its value.
    current_xpack_security_setting = check_xpack_security_setting(config_file_path)

    # If the setting doesn't exist, add it to the configuration file.
    if current_xpack_security_setting is None:
        with open(config_file_path, 'a') as file:
            file.write(f'{xpack_setting_to_set}\n')
        if output_message:
            print(f"Added [{xpack_setting_to_set}] to the configuration.")
    # If the setting exists and is different from the desired setting, change it.
    elif current_xpack_security_setting != setting:
        with open(config_file_path, 'r') as file:
            lines = file.readlines()
        with open(config_file_path, 'w') as file:
            for line in lines:
                if f"{XPACK_SECURITY_SETTING_NAME}:" in line:
                    file.write(f'{xpack_setting_to_set}\n')
                else:
                    file.write(line)
        if output_message:
            print(f"Changed [{XPACK_SECURITY_SETTING_NAME}] to [{setting}].")
    # If the setting is already set to the desired value, print a message.
    elif current_xpack_security_setting == setting:
        if output_message:
            print(f"The setting is already set to [{setting}].")
            return 0

    # Check if the setting was really set.
    if check_xpack_security_setting() is setting:
        console.print(f"The setting is confirmed to be [{XPACK_SECURITY_SETTING_NAME}: {str(setting).lower()}].", style='green', markup=False)
        return 0
    else:
        console.print(f"Failed to set [{XPACK_SECURITY_SETTING_NAME}: {str(setting).lower()}].", style='red', markup=False)
        return 1


def is_4gb_memory_heap_options_applied_on_server() -> bool:
    """
    The function checks if the 4GB memory heap options are applied on the Elasticsearch server.
    :return: bool.
    """

    try:
        response = requests.get(DEFAULT_ELASTIC_URL_JVM_OPTIONS, timeout=10)
        response.raise_for_status()
        data = response.json()
    except (requests.RequestException, ValueError) as e:
        console.print(str(e), style='red', markup=False)
        return False

    nodes = data.get("nodes") or {}
    if not nodes:
        console.print("No nodes found in the Elasticsearch response.", style='red', markup=False)
        return False

    # Check if memory heap options are applied in 'input_arguments' key.
    for node in data['nodes'].values():
        # Get the JVM input arguments values.
        input_arguments = node['jvm']['input_arguments']

        # Check that the 4GB memory heap options are applied.
        options_result: bool = all(options in input_arguments for options in ELASTIC_JVM_OPTIONS_4GB_MEMORY_USAGE)
        if options_result:
            return True

    return False


def create_jvm_options_custom_file(file_path: str, options: list):
    """
    The function creates a custom JVM options file for Elasticsearch.
    You can use the default directory path as 'ELASTIC_JVM_OPTIONS_DIRECTORY'.
    :param file_path: str, the path to the custom JVM options file.
    :param options: list, the list of JVM options.
    :return:
    """

    # Write the options to the file.
    with open(file_path, 'w') as file:
        for option in options:
            file.write(f"{option}\n")


def create_jvm_options_custom_4gb_memory_heap_file(file_path: str = None):
    """
    The function creates a custom JVM options file with 4GB memory heap usage.
    The 4GB memory usage options are needed for the Elasticsearch to work properly and not to crash.
    :param file_path: str, the path to the custom JVM options file.
    :return:
    """

    if not file_path:
        file_path = ELASTIC_JVM_OPTIONS_4GB_CUSTOM_FILE

    create_jvm_options_custom_file(file_path, ELASTIC_JVM_OPTIONS_4GB_MEMORY_USAGE)


def is_server_available(
        max_attempts: int = 5,
        wait_between_attempts_seconds: float = 10,
        elastic_url: str = None
) -> bool:
    """
    The function checks if Elasticsearch server is up and running by sending GET request to the Elasticsearch server.
    :param max_attempts: int, the maximum number of attempts to check if Elasticsearch is running.
    :param wait_between_attempts_seconds: float, the time to wait between attempts.
    :param elastic_url: str, the URL of the Elasticsearch server. If None, the default URL will be used.
    :return: bool, True if Elasticsearch server is running/connectable, False otherwise.
    """

    if not elastic_url:
        elastic_url = DEFAULT_ELASTIC_URL

    for attempt in range(1, max_attempts + 1):
        print(f"Checking if Elasticsearch is running (Attempt {attempt}/{max_attempts})...")

        try:
            response = requests.get(elastic_url)
            status_code = response.status_code

            if status_code == 200:
                console.print("Elasticsearch is up and running.", style='green')
                return True
            else:
                console.print(f"Elasticsearch is not running. Status code: {status_code}", style='yellow')
        except requests.exceptions.RequestException as e:
            console.print(f"Failed to connect to Elasticsearch: {e}", style='yellow')

        print("Waiting for Elasticsearch to start...")
        time.sleep(wait_between_attempts_seconds)

    console.print("Elasticsearch did not start within the expected time.", style='red')
    return False


def main(
        install_search: bool = True,
        install_kibana: bool = True,
        disable_xpack_security: bool = False,
        enable_4gb_jvm_options: bool = False
):
    """
    Install Elastic Elasticsearch and Kibana on the current platform.

    :param install_search: bool, if True, install Elastic Elasticsearch.
    :param install_kibana: bool, if True, install Elastic Kibana.
    :param disable_xpack_security: bool, if True, disable xpack security in the Elasticsearch configuration.
        Set: {xpack.security.enabled: false}
    :param enable_4gb_jvm_options: bool, if True, create custom JVM options file with 4GB memory usage.

    :return: int, 0 if successful, 1 if an error occurred.
    """

    if not install_search and not install_kibana:
        raise ValueError("At least one of the services (Elasticsearch or Kibana) must be installed.")

    if not permissions.is_admin():
        console.print("This script requires root privileges...", style='red')
        return 1

    ubuntu_terminal.update_system_packages()
    ubuntu_terminal.install_packages(UBUNTU_DEPENDENCY_PACKAGES)

    # Install the GPG key and add elastic repository.
    script = f"""
        # Download and install the GPG signing key
        wget -qO - https://artifacts.elastic.co/GPG-KEY-elasticsearch | gpg --dearmor | sudo tee /usr/share/keyrings/elasticsearch-keyring.gpg > /dev/null

        # Add the Elastic repository to the system
        echo "deb [signed-by=/usr/share/keyrings/elasticsearch-keyring.gpg] https://artifacts.elastic.co/packages/8.x/apt stable main" | sudo tee /etc/apt/sources.list.d/elastic-8.x.list
        """

    process.execute_script(script, shell=True)

    # Update system with elastic search packages.
    ubuntu_terminal.update_system_packages()

    if install_search:
        # Install Elasticsearch.
        ubuntu_terminal.install_packages([UBUNTU_ELASTIC_PACKAGE_SERVICE_NAME])

        if disable_xpack_security:
            result_code: int = modify_xpack_security_setting(setting=False, output_message=True)
            if result_code != 0:
                return result_code

        # Start, enable and check the Elasticsearch service.
        result_code: int = ubuntu_terminal.start_enable_service_check_availability(UBUNTU_ELASTIC_PACKAGE_SERVICE_NAME)
        if result_code != 0:
            return result_code

        # Check if Elasticsearch is running.
        if not is_server_available():
            return 1

        console.print(f"Installation completed. Default Elasticsearch on {DEFAULT_ELASTIC_URL}", style='green')

    if install_kibana:
        # Install Kibana.
        ubuntu_terminal.install_packages([UBUNTU_KIBANA_PACKAGE_SERVICE_NAME])

        # Start and enable Kibana service.
        result_code: int = ubuntu_terminal.start_enable_service_check_availability(UBUNTU_KIBANA_PACKAGE_SERVICE_NAME)
        if result_code != 0:
            return result_code

        console.print(f"Installation completed. Default Kibana on {DEFAULT_KIBANA_URL}", style='green')

    if not install_search and disable_xpack_security:
        result_code: int = modify_xpack_security_setting(setting=False, output_message=True)
        if result_code != 0:
            return result_code

    if enable_4gb_jvm_options:
        print("Creating custom JVM options file with 4GB memory usage.")
        create_jvm_options_custom_4gb_memory_heap_file()

        if is_4gb_memory_heap_options_applied_on_server():
            console.print("4GB memory heap options are applied on the server.", style='green')
        else:
            console.print("4GB memory heap options are NOT applied on the server.", style='red')
            console.print("You may need to restart the Elasticsearch service manually.", style='yellow')
            return 1

    return 0


def _make_parser():
    parser = argparse.ArgumentParser(description='Install Elastic Elasticsearch / Kibana; Automate some of the settings.')

    parser.add_argument(
        '-is', '--install-search',
        action='store_true',
        help='Install Elastic Elasticsearch.'
    )
    parser.add_argument(
        '-ik', '--install-kibana',
        action='store_true',
        help='Install Elastic Kibana.'
    )

    parser.add_argument(
        '-dxs', '--disable-xpack-security',
        action='store_true',
        help="Disable xpack security in the Elasticsearch configuration, set: {xpack.security.enabled: false}\n"
             "If you're using this not during installation, you'll need to restart Elasticsearch service manually."
    )
    parser.add_argument(
        '-j4g', '--enable-4gb-jvm-options',
        action='store_true',
        help=f'Create custom JVM options file with 4GB memory usage: {ELASTIC_JVM_OPTIONS_4GB_MEMORY_USAGE}'
    )

    return parser


if __name__ == '__main__':
    exec_parser = _make_parser()
    args = exec_parser.parse_args()
    sys.exit(main(**vars(args)))