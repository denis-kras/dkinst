import json
import re
import shutil
import subprocess
import tempfile
import urllib.request
from dataclasses import dataclass
from typing import Optional, Tuple
import argparse
import sys

from rich.console import Console

from atomicshop import web

from .infra import permissions


console = Console()


VERSION: str = "1.0.0"
# Initial version

DIST_URL = "https://npcap.com/dist/"
USER_AGENT = web.USER_AGENTS['Chrome 142.0.0 Windows 10/11 x64']

WINDOW_TITLE: str = "Npcap"


def install_npcap(
        try_automation: bool = False,
) -> int:
    """
    Install the latest Npcap on Windows by downloading from the official Npcap release archive.

    Notes:
    - Silent install (/S) is available ONLY with Npcap OEM. The public/free installer does not support silent mode.
      See Npcap Users' Guide. https://npcap.com/guide/npcap-users-guide.html
    - This script can:
      * download the latest installer from https://npcap.com/dist/
      * optionally verify Authenticode signature (recommended)
      * run installer (GUI by default; silent only if you pass --silent and have an OEM installer)
      * verify installation by checking the "npcap" driver service

    :param try_automation: bool: Try to install through GUI automation. TRY AT YOUR OWN RISK!
                                    Since Npcap public installer does not support silent mode, only the OEM version.
                                        GUI automation may fail if the installer UI changes or mess buttons on your system, resulting in
                                        a broken installation/system crash.
    :return: int: Installer exit code.
    """

    @dataclass(frozen=True)
    class LatestInfo:
        version: str
        exe_url: str
        exe_name: str

    def http_get_text(url: str, timeout: int = 30) -> str:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def parse_latest_from_dist(html_string: str) -> LatestInfo:
        """
        Parse https://npcap.com/dist/ to determine latest release and installer filename.

        Strategy:
        1) Prefer explicit sentence: "The latest Npcap release is version X.YY."
        2) Fall back to scanning for npcap-<ver>.exe and picking max version.
        """
        m = re.search(r"The latest Npcap release is version\s+([0-9]+(?:\.[0-9]+)+)\s*\.", html_string, re.IGNORECASE)
        versions_found = re.findall(r"npcap-([0-9]+(?:\.[0-9]+)+)\.exe", html_string, re.IGNORECASE)

        chosen_ver: Optional[str] = m.group(1) if m else None

        if not chosen_ver:
            if not versions_found:
                raise RuntimeError("Could not find any Npcap installer versions in dist page HTML.")
            chosen_ver = max(versions_found, key=version_key)

        exe_name = f"npcap-{chosen_ver}.exe"
        exe_url = DIST_URL.rstrip("/") + "/" + exe_name
        return LatestInfo(version=chosen_ver, exe_url=exe_url, exe_name=exe_name)

    def version_key(v: str) -> Tuple[int, ...]:
        return tuple(int(x) for x in v.split("."))

    def verify_authenticode_signature(path: str) -> None:
        ps = shutil.which("powershell") or shutil.which("pwsh")
        if not ps:
            raise RuntimeError("PowerShell not found (powershell/pwsh). Required for signature check.")

        ps_script = r"""
    $ErrorActionPreference = 'Stop'
    & {
      param([Parameter(Mandatory=$true)][string]$Path)

      $sig = Get-AuthenticodeSignature -LiteralPath $Path

      $obj = [pscustomobject]@{
        Status        = $sig.Status.ToString()
        StatusMessage = $sig.StatusMessage
        SignerSubject = if ($sig.SignerCertificate) { $sig.SignerCertificate.Subject } else { $null }
      }

      # Write exactly one JSON line to stdout
      [Console]::WriteLine(($obj | ConvertTo-Json -Compress))
    }
    """.strip()  # CRITICAL: prevents the appended arg from landing on a new line

        completed = subprocess.run(
            [ps, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
             "-Command", ps_script, path],
            capture_output=True,
            text=True,
        )

        if completed.returncode != 0:
            raise RuntimeError(
                "PowerShell signature check failed.\n"
                f"Exit: {completed.returncode}\n"
                f"STDOUT: {completed.stdout}\n"
                f"STDERR: {completed.stderr}"
            )

        out = completed.stdout.strip()
        if not out:
            # Include stderr here too; in this failure mode PowerShell often wrote the real reason to stderr
            raise RuntimeError(
                "PowerShell returned no output for signature check.\n"
                f"STDERR: {completed.stderr}"
            )

        # If anything extra sneaks into stdout, take the last non-empty line as the JSON payload.
        last_line = next((line for line in reversed(out.splitlines()) if line.strip()), "")
        data = json.loads(last_line)

        if data.get("Status") != "Valid":
            raise RuntimeError(
                f"Installer signature is not valid (Status={data.get('Status')}). "
                f"Message: {data.get('StatusMessage')}. "
                f"Signer: {data.get('SignerSubject')}"
            )

    def run_installer_wait(
            file_path: str,
            automation: bool = False
    ) -> int:
        """
        Run an installer EXE directly and wait for completion.
        Returns the installer's exit code.

        Important:
        - For GUI installers, this blocks until the installer process exits.
        - Some installers spawn child processes and exit early; if that happens,
          we can add a more advanced wait strategy. (Npcap typically does not.)
        """

        from .infra import gui_interaction

        cmd = [file_path]
        proc = subprocess.Popen(cmd)

        if automation:
            # Define the required UI steps (text, timeout seconds).
            # Adjust timeouts and labels to match the installer screens you actually see.
            steps = [
                ("I Agree", 60.0),
                ("Install", 60.0),
                ("Next", 240.0),
                ("Finish", 300.0),
            ]

            for text, t in steps:
                # If installer exits early, treat as error (per your earlier requirement).
                rc = proc.poll()
                if rc is not None:
                    raise RuntimeError(
                        f'Installer exited with code {rc} before "{text}" was found/clicked.'
                    )

                clicked = gui_interaction.click_button(
                    text,
                    window_title=WINDOW_TITLE,
                    window_title_partial=True,
                    pid=proc.pid,
                    timeout=t,
                    poll_interval=0.2,
                    relax_pid_after=5.0,  # after 5s, allow pid=None in case UI is in a spawned process
                    focus_before_click=True,
                )

                if not clicked:
                    # Enforce "exit with error" behavior: terminate installer and raise.
                    # taskkill /T kills child processes as well.
                    subprocess.run(
                        ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                        capture_output=True,
                        text=True,
                    )
                    scope = (
                        f' (window title regex: {WINDOW_TITLE.pattern})'
                        if isinstance(WINDOW_TITLE, re.Pattern)
                        else f' (window title: {WINDOW_TITLE})'
                        if isinstance(WINDOW_TITLE, str)
                        else " (all windows)"
                    )
                    raise RuntimeError(f'Button "{text}" was not visible+enabled within {t:.0f}s{scope}.')

        # All required buttons clicked; wait for installer completion and return its exit code.
        return proc.wait()

    def sc_query(service_name: str) -> Tuple[int, str]:
        completed = subprocess.run(
            ["sc.exe", "query", service_name],
            capture_output=True,
            text=True,
        )
        return completed.returncode, (completed.stdout + "\n" + completed.stderr).strip()

    if not permissions.is_admin():
        console.print("This script requires administrative privileges to run.", style="red")
        return 1

    # Discover latest
    print(f"Fetching latest version info from {DIST_URL} ...")
    html = http_get_text(DIST_URL)
    latest = parse_latest_from_dist(html)
    print(f"Latest Npcap version: {latest.version}")
    print(f"Installer URL: {latest.exe_url}")

    # Download
    download_dir = tempfile.mkdtemp(prefix="npcap-install-")
    # exe_path = os.path.join(download_dir, latest.exe_name)
    # print(f"Downloading to: {exe_path}")
    exe_path = web.download(file_url=latest.exe_url, target_directory=download_dir, file_name=latest.exe_name)

    # Signature check
    print("Verifying Authenticode signature ...")
    verify_authenticode_signature(exe_path)
    print("Signature status: Valid")

    rc = run_installer_wait(exe_path, automation=try_automation)

    # Interpret installer exit code (per Npcap Users' Guide)
    if rc == 0:
        print("Installer completed successfully (exit code 0).")
    elif rc == 3010:
        print("Installer succeeded but a reboot is required (exit code 3010).")
    elif rc == 350:
        print("Installer failed; reboot and try again (exit code 350).")
    elif rc == 1:
        print("Installer aborted by user (exit code 1).")
    elif rc == 2:
        print("Installer aborted by script (exit code 2).")
    else:
        print(f"Installer exited with code {rc}.")

    # Verify installation by checking the npcap driver service
    sc_rc, sc_out = sc_query("npcap")
    if sc_rc == 0 and re.search(r"SERVICE_NAME:\s*npcap", sc_out, re.IGNORECASE):
        print("Verification: 'npcap' service is present.")
    else:
        print("Verification: 'npcap' service not confirmed via 'sc query npcap'.")
        print("sc output:")
        print(sc_out)

    # Cleanup
    shutil.rmtree(download_dir, ignore_errors=True)

    # Return the installer's exit code.
    return rc


def _make_parser():
    """
    Parse command line arguments.

    :return: Parsed arguments.
    """
    parser = argparse.ArgumentParser(description='Install Npcap.')
    parser.add_argument(
        '--try-automation', action='store_true',
        help='Will try to install through GUI automation. TRY AT YOUR OWN RISK! \n'
             'Since Npcap public installer does not support silent mode, only the OEM version.\n'
             'GUI automation may fail if the installer UI changes or mess buttons on your system, resulting in a broken installation/system crash.')
    parser.add_argument(
        '--force', action='store_true',
        help='Force the installation')

    return parser


def main(
        try_automation: bool = False,
        force: bool = False
) -> int:
    """
    The function will install PyCharm on Ubuntu or Windows.

    :param try_automation: bool: Try to install through GUI automation. TRY AT YOUR OWN RISK!
                                 Since Npcap public installer does not support silent mode, only the OEM version.
                                    GUI automation may fail if the installer UI changes or mess buttons on your system, resulting in
                                    a broken installation/system crash.
    :param force: bool: Force the installation.

    :return: int: 0 if success, 1 if error.
    """

    if try_automation and not force:
        # Ask the user for confirmation
        console.print("WARNING: You have chosen to install Npcap using GUI automation. "
                      "This method may fail if the installer UI changes or if there are unexpected prompts. "
                      "This could potentially lead to a broken installation or system issues.", style="yellow")
        response = input("Do you want to proceed? (yes/no): ").strip().lower()
        if response not in ('yes', 'y'):
            console.print("Installation aborted by user.", style="red")
            return 1

    return install_npcap(try_automation=try_automation)


if __name__ == '__main__':
    pycharm_parser = _make_parser()
    args = pycharm_parser.parse_args()
    sys.exit(main(**vars(args)))