import subprocess
import sys


def is_pip_package_installed(package: str) -> bool:
    return (
        subprocess.run(
            [sys.executable, "-m", "pip", "show", package],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ).returncode
        == 0
    )


def pip_install(package: str) -> int:
    in_venv = (
        getattr(sys, "base_prefix", sys.prefix) != sys.prefix
        or hasattr(sys, "real_prefix")
    )

    base_cmd = [sys.executable, "-m", "pip", "install", "--upgrade", package]
    user_cmd = [sys.executable, "-m", "pip", "install", "--user", "--upgrade", package]

    # Prefer non-user installs inside venv; prefer --user installs outside venv.
    attempts = [base_cmd, user_cmd] if in_venv else [user_cmd, base_cmd]

    last_rc = 1
    for cmd in attempts:
        last_rc = subprocess.run(cmd).returncode
        if last_rc == 0:
            return 0
    return last_rc


def pip_uninstall(package: str) -> int:
    if '==' in package:
        # pip uninstall doesn't support version specifiers, so strip them if present.
        package = package.split('==')[0]

    if not is_pip_package_installed(package):
        return 0
    return subprocess.run(
        [sys.executable, "-m", "pip", "uninstall", "-y", package]
    ).returncode