import subprocess


def run_command(
        command: str,
        timeout=None
) -> tuple[int, str, str]:
    """
    Run Add-AppxPackage and return (returncode, stdout, stderr).
    Does NOT raise on failure; check returncode yourself.

    ================================

    Example:
    command = f"Add-AppxPackage -Path {quoted_path} -ForceApplicationShutdown -ForceUpdateFromAnyVersion {extra}"
    rc, stdout, stderr = powershells.run_command(command=command, timeout=timeout)
        if rc != 0:
            if "HRESULT: 0x80073D06, The package could not be installed because a higher version of this package is already installed" in stderr:
                console.print(f'Appx {appx_file_path} is already installed with a higher version. Skipping.', style='yellow')
            else:
                console.print(f'Failed to add Appx: {appx_file_path}', style='red')
                console.print(stderr, style='red')
                return rc
    """

    # Force UTF-8 so Python decodes reliably, and make errors terminate the script
    # so we get a non-zero exit code.
    ps_cmd = (
        "[Console]::OutputEncoding=[System.Text.UTF8Encoding]::new();"
        "$ErrorActionPreference='Stop';"
        "$ProgressPreference='SilentlyContinue';"
        f"try {{ {command} }} "
        "catch { Write-Error $_; exit 1 }"
    )

    proc = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", ps_cmd],
        capture_output=True,  # captures both stdout and stderr
        text=True,
        encoding="utf-8",     # matches OutputEncoding above
        timeout=timeout
    )
    return proc.returncode, proc.stdout, proc.stderr