import sys
import argparse
import subprocess
import json
import time
import urllib.request
import os
import tempfile
from pathlib import Path

from .infra.printing import printc


VERSION: str = "1.0.0"
"""Initial"""


VSWHERE_EXE: Path = Path(
    os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
) / "Microsoft Visual Studio" / "Installer" / "vswhere.exe"


def is_msvc_installed():
    if not VSWHERE_EXE.exists():
        return False

    try:
        out = subprocess.check_output(
            f'"{VSWHERE_EXE}" -latest -products Microsoft.VisualStudio.Product.BuildTools -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -format json',
            shell=True, text=True)
        return bool(json.loads(out))
    except subprocess.CalledProcessError:
        return False


def run(cmd, *, ok=(0,), **kw):
    print(f"[+] {cmd}")
    process_instance = subprocess.run(cmd, shell=True, **kw)
    if process_instance.returncode not in ok:
        raise subprocess.CalledProcessError(process_instance.returncode, cmd)


def install_build_tools() -> int:
    print("Installing Visual Studio 2022 Build Tools + C++ workload …")
    url = "https://aka.ms/vs/17/release/vs_BuildTools.exe"
    with tempfile.TemporaryDirectory() as td:
        exe = Path(td) / "vs_BuildTools.exe"
        urllib.request.urlretrieve(url, exe)
        run(
            f'"{exe}" --passive --wait --norestart '
            '--add Microsoft.VisualStudio.Workload.VCTools --includeRecommended',
            ok=(0, 3010, 1641))
    print("Waiting for Build Tools to register …")
    for _ in range(60):
        if is_msvc_installed():
            return 0
        time.sleep(5)

    printc("Timed out waiting for Build Tools to register.", color="red")
    return 1


def _make_parser():
    parser = argparse.ArgumentParser(description="Install Microsoft Visual Studio Build Tools 2022 on Windows.")
    parser.add_argument(
        '-i', '--install',
        action='store_true',
        help=f"Install."
    )
    parser.add_argument(
        '-ii', '--is-installed',
        action='store_true',
        help=f"Check if MS VS Build Tools are installed."
    )

    parser.add_argument(
        '-f', '--force',
        action='store_true',
        help="Force installation, even if winget is already installed."
    )

    return parser


def main(
        install: bool = False,
        is_installed: bool = False,
        force: bool = False,
) -> int:
    """
    The function will install MS VS Build Tools 2022 on Windows.

    :param install: bool, If True, install Build Tools.
    :param is_installed: bool, If True, check if Build Tools is installed.
    :param force: bool, If True, force installation even if Build Tools are already installed

    :return: int, Return code of the installation process. 0 if successful, non-zero otherwise.
    """

    if not install and not is_installed:
        printc("No method specified. Use --help for more information.", color="red")
        return 1
    if install and is_installed:
        printc("Please specify only one method at a time.", color="red")
        return 1

    if is_installed:
        if is_msvc_installed():
            printc("MS VS Build Tools 2022 is installed.", color="green")
            return 0
        else:
            printc("MS VS Build Tools 2022 is not installed.", color="red")
            return 1

    if install:
        if not force and is_msvc_installed():
            printc("MS VS Build Tools 2022 is already installed. Use [force] to reinstall", color="yellow")
            return 0
        return install_build_tools()

    return 0


if __name__ == '__main__':
    nodejs_parser = _make_parser()
    args = nodejs_parser.parse_args()
    sys.exit(main(**vars(args)))