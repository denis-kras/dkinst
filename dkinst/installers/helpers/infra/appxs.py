import subprocess

from . import powershells


def _ps_quote(s: str) -> str:
    """Quote a string for PowerShell single-quoted literals."""
    return "'" + s.replace("'", "''") + "'"


def add_appx_by_file(
        path: str,
        extra_args=None,
        timeout=None
):
    """
    Run Add-AppxPackage and return (returncode, stdout, stderr).
    Does NOT raise on failure; check returncode yourself.

    ================================

    Example:
    rc, stdout, stderr = appxs.add_appx(appx_file_path)
        if rc != 0:
            if "HRESULT: 0x80073D06, The package could not be installed because a higher version of this package is already installed" in stderr:
                console.print(f'Appx {appx_file_path} is already installed with a higher version. Skipping.', style='yellow')
            else:
                console.print(f'Failed to add Appx: {appx_file_path}', style='red')
                console.print(stderr, style='red')
                return rc
    """
    if extra_args is None:
        extra_args = []

    quoted_path = _ps_quote(path)
    extra = " ".join(extra_args)

    command = f"Add-AppxPackage -Path {quoted_path} -ForceApplicationShutdown -ForceUpdateFromAnyVersion {extra}"
    return powershells.run_command(command=command, timeout=timeout)


def register_appx_by_family_name(
        family_name: str,
        timeout=None
) -> tuple[int, str, str]:
    """
    Run Add-AppxPackage -RegisterByFamilyName and return (returncode, stdout, stderr).
    Does NOT raise on failure; check returncode yourself.

    ================================

    Example:
    rc, stdout, stderr = appxs.register_appx_by_family_name("Microsoft.DesktopAppInstaller_8wekyb3d8bbwe")
        if rc != 0:
            console.print(f'Failed to register the WinGet package.', style='red')
            console.print(stderr, style='red')
            return rc
    """

    quoted_family_name = _ps_quote(family_name)

    command = f"Add-AppxPackage -RegisterByFamilyName -MainPackage {quoted_family_name}"
    return powershells.run_command(command=command, timeout=timeout)