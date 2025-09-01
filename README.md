<h1 align="center">Den K Simple Installer - dkinst</h1>



<!-- ABOUT THE PROJECT -->
## About The Project


dkinst is a simple installer mostly for my professional needs, in case I need a one-click installer for a library or a tool.
So, I will not search for a setup script/line or write one.
It is written in Python, currently supports 3.12. Hope to support newer versions in the near future.


<!-- AVAILABLE INSTALLERS -->
## Available Installers

You can check the 'installers' folder for the available installers.
Or execute in CMD:
```cmd
dkinst available
```


<!-- GETTING STARTED -->
## Getting Started

To get a local copy up and running follow these simple steps.

### Installation Windows

1. Install Python 3.12.10 or use the silent installer that will download and install it for you.<br>
    1.1. Download the file: install_python_as_admin.cmd<br>
    1.2. Run CMD as admin.<br>
    1.3. In CMD run the script with '3.12.10' argument:
    ```cmd
   install_python_as_admin.cmd 3.12.10
   ```
   <br>
2. Install the library using pip:
   ```cmd
   pip install dkinst
   ```
   
### Installation Linux
   
Ubuntu 24 already comes with python 3.12, just use pip to install the library:
   ```sh
   pip install dkinst
   ```

<!-- USAGE EXAMPLES -->
## Usage

Execute in CMD:
```cmd
dkinst
dkinst help
```
For full help and examples about installation commands.



<!-- LICENSE -->
## License

Distributed under the MIT License. See `LICENSE.txt` for more information.



<!-- HISTORY -->
## History

[History.md](https://github.com/BugSec-Official/atomicshop/blob/main/History.md#history)