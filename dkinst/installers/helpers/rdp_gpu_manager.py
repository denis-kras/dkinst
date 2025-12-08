"""
RDP GPU tuning helper for Windows.

This script manipulates the registry values that back these Group Policy settings:

- Use hardware graphics adapters for all Remote Desktop Services sessions
- Configure H.264/AVC hardware encoding for Remote Desktop Connections
- Prioritize H.264/AVC 444 graphics mode for Remote Desktop Connections
- Use WDDM graphics display driver for Remote Desktop Connections

It follows the workflow described in the “Enable GPU Acceleration over Remote Desktop (Windows 10)”
guide and uses the documented policy backing keys under:

  HKLM\SOFTWARE\Policies\Microsoft\Windows NT\Terminal Services
"""

import argparse
import sys
import subprocess
from typing import Literal

from .infra import permissions, registrys

Action = Literal["enable", "disable", "default"] | None


SCRIPT_NAME: str = "Windows RDP GPU Driver Manager"
AUTHOR: str = "Denis Kras"
VERSION: str = "1.0.0"
RELEASE_COMMENT: str = "Initial."


TERMINAL_SERVICES_KEY = r"SOFTWARE\Policies\Microsoft\Windows NT\Terminal Services"


# ----------------- Feature functions -----------------


def set_gpu_registry(
        action: Action,
        dry_run: bool = False,
        verbose: bool = False,
) -> None:
    """
    Use hardware graphics adapters for all Remote Desktop Services sessions.

    Policy value:
      HKLM\SOFTWARE\Policies\Microsoft\Windows NT\Terminal Services\bEnumerateHWBeforeSW
        enable  -> 1
        disable -> 0
        default -> delete value (Not configured)
    """
    if action == "enable":
        registrys.set_policy_dword("bEnumerateHWBeforeSW", 1, TERMINAL_SERVICES_KEY, "HKLM", dry_run, verbose)
    elif action == "disable":
        registrys.set_policy_dword("bEnumerateHWBeforeSW", 0, TERMINAL_SERVICES_KEY, "HKLM", dry_run, verbose)
    elif action == "default":
        registrys.delete_policy_value("bEnumerateHWBeforeSW", TERMINAL_SERVICES_KEY, "HKLM", dry_run, verbose)
    else:
        raise ValueError(f"Unknown action for GPU registry: {action!r}")


def set_hw_encoding_registry(
        action: Action,
        dry_run: bool = False,
        verbose: bool = False,
) -> None:
    """
    Configure H.264/AVC hardware encoding for Remote Desktop Connections.

    Policy value:
      HKLM\SOFTWARE\Policies\Microsoft\Windows NT\Terminal Services\AVCHardwareEncodePreferred
        enable  -> 1
        disable -> 0
        default -> delete value (Not configured)
    """
    if action == "enable":
        registrys.set_policy_dword("AVCHardwareEncodePreferred", 1, TERMINAL_SERVICES_KEY, "HKLM", dry_run, verbose)
    elif action == "disable":
        registrys.set_policy_dword("AVCHardwareEncodePreferred", 0, TERMINAL_SERVICES_KEY, "HKLM", dry_run, verbose)
    elif action == "default":
        registrys.delete_policy_value("AVCHardwareEncodePreferred", TERMINAL_SERVICES_KEY, "HKLM", dry_run, verbose)
    else:
        raise ValueError(f"Unknown action for HW encoding registry: {action!r}")


def set_avc444_registry(
        action: Action,
        dry_run: bool = False,
        verbose: bool = False,
) -> None:
    """
    Prioritize H.264/AVC 444 graphics mode for Remote Desktop Connections.

    Policy value:
      HKLM\SOFTWARE\Policies\Microsoft\Windows NT\Terminal Services\AVC444ModePreferred
        enable  -> 1
        disable -> 0
        default -> delete value (Not configured)
    """
    if action == "enable":
        registrys.set_policy_dword("AVC444ModePreferred", 1, TERMINAL_SERVICES_KEY, "HKLM", dry_run, verbose)
    elif action == "disable":
        registrys.set_policy_dword("AVC444ModePreferred", 0, TERMINAL_SERVICES_KEY, "HKLM", dry_run, verbose)
    elif action == "default":
        registrys.delete_policy_value("AVC444ModePreferred", TERMINAL_SERVICES_KEY, "HKLM", dry_run, verbose)
    else:
        raise ValueError(f"Unknown action for AVC444 registry: {action!r}")


def set_wddm_registry(
        action: Action,
        dry_run: bool = False,
        verbose: bool = False,
) -> None:
    """
    Use WDDM graphics display driver for Remote Desktop Connections.

    Policy value:
      HKLM\SOFTWARE\Policies\Microsoft\Windows NT\Terminal Services\fEnableWddmDriver
        enable  -> 1
        disable -> 0
        default -> delete value (Not configured)
    """
    if action == "enable":
        registrys.set_policy_dword("fEnableWddmDriver", 1, TERMINAL_SERVICES_KEY, "HKLM", dry_run, verbose)
    elif action == "disable":
        registrys.set_policy_dword("fEnableWddmDriver", 0, TERMINAL_SERVICES_KEY, "HKLM", dry_run, verbose)
    elif action == "default":
        registrys.delete_policy_value("fEnableWddmDriver", TERMINAL_SERVICES_KEY, "HKLM", dry_run, verbose)
    else:
        raise ValueError(f"Unknown action for WDDM registry: {action!r}")


# ----------------- Troubleshooting helpers -----------------


def restart_rdp_termservice_service(
        dry_run: bool = False,
        verbose: bool = False
) -> None:
    """
    Restart the Remote Desktop Services (TermService) service.

    WARNING: This will immediately disconnect ALL active RDP sessions.
    """

    if dry_run:
        print("[DRY-RUN] Would restart 'Remote Desktop Services' (TermService) service.")
        return

    if verbose:
        print("Stopping 'Remote Desktop Services' (TermService)...")

    try:
        result_stop = subprocess.run(
            ["sc", "stop", "TermService"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        if verbose:
            print(result_stop.stdout)
    except subprocess.CalledProcessError as e:
        print("Error while stopping TermService:", file=sys.stderr)
        print(e.stdout, file=sys.stderr)
        return

    if verbose:
        print("Starting 'Remote Desktop Services' (TermService)...")

    try:
        result_start = subprocess.run(
            ["sc", "start", "TermService"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        if verbose:
            print(result_start.stdout)
    except subprocess.CalledProcessError as e:
        print("Error while starting TermService:", file=sys.stderr)
        print(e.stdout, file=sys.stderr)
        return

    print("Remote Desktop Services (TermService) restarted successfully.")


def print_status() -> None:
    mapping = {
        "bEnumerateHWBeforeSW": "Use hardware graphics adapters for all Remote Desktop Services sessions",
        "AVCHardwareEncodePreferred": "Configure H.264/AVC hardware encoding for Remote Desktop Connections",
        "AVC444ModePreferred": "Prioritize H.264/AVC 444 graphics mode for Remote Desktop Connections",
        "fEnableWddmDriver": "Use WDDM graphics display driver for Remote Desktop Connections",
    }
    print(f"Current values under HKLM\\{TERMINAL_SERVICES_KEY}:")
    for value_name, label in mapping.items():
        val = registrys.get_policy_dword(value_name, TERMINAL_SERVICES_KEY, "HKLM")
        if val is None:
            print(f"  {label} ({value_name}): <not set>")
        else:
            print(f"  {label} ({value_name}): {val}")


def print_diagnostics() -> None:
    # Based on the verification/troubleshooting steps in your PDF guide. :contentReference[oaicite:0]{index=0}
    print("Verification and troubleshooting tips:")
    print()
    print("  1) Apply the settings")
    print("     - After changing values, sign out of the RDP session or reboot the host so")
    print("       the Remote Desktop Session Host picks up the new policy values.")
    print()
    print("  2) Verify GPU rendering is used")
    print("     - On the HOST, open Task Manager.")
    print("     - Go to Performance -> GPU.")
    print("     - While connected via RDP, run a 3D or GPU-heavy app in the session.")
    print("     - Watch the 3D and Video Encode engines; they should show activity.")
    print()
    print("  3) Verify AVC/H.264 and 4:4:4 mode")
    print("     - On the HOST, open Event Viewer.")
    print("     - Go to:")
    print("         Applications and Services Logs")
    print("           -> Microsoft")
    print("           -> Windows")
    print("           -> RemoteDesktopServices-RdpCoreTS")
    print("     - Look for Event ID 162:")
    print("         * 'AVC Available: 1' means H.264/AVC is active.")
    print("         * For 4:4:4 mode, the event shows profile 2048.")
    print()
    print("  4) If you see a black screen or visual glitches:")
    print("     - Try disabling AVC444 and/or hardware encoding while leaving GPU adapter")
    print("       enabled (use --disable-avc444 and/or --disable-hw-encode).")
    print("     - Try toggling the WDDM graphics display driver (--enable-wddm/--disable-wddm).")
    print("     - Make sure your GPU drivers are up to date.")
    print("     - For NVIDIA datacenter GPUs, ensure the GPU is in WDDM mode, not TCC.")
    print()
    print("  5) OpenGL apps")
    print("     - Some OpenGL apps may still fall back to software rendering over RDP;")
    print("       this is a limitation of how they talk to the GPU.")


# ----------------- Argparse setup -----------------


def _make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Enable/disable GPU-related Remote Desktop policies via the registry."
    )

    feature = parser.add_argument_group("Feature toggles")

    # Mutually exclusive action: exactly one of these (or none if you only want --status/--diagnostics)
    action_group = feature.add_mutually_exclusive_group()
    action_group.add_argument(
        "--enable",
        dest="enable",
        action="store_true",
        help="Set selected settings to Enabled.",
    )
    action_group.add_argument(
        "--disable",
        dest="disable",
        action="store_true",
        help="Set selected settings to Disabled.",
    )
    action_group.add_argument(
        "--default",
        dest="default_state",
        action="store_true",
        help="Reset selected settings to OS default (Not configured, delete policy values).",
    )

    # Targets: which settings to act on. If none are specified, ALL are targeted.
    feature.add_argument(
        "--gpu",
        dest="gpu",
        action="store_true",
        help="Target 'Use hardware graphics adapters for all Remote Desktop Services sessions'.",
    )
    feature.add_argument(
        "--hw-encode",
        dest="hw_encode",
        action="store_true",
        help="Target 'Configure H.264/AVC hardware encoding for Remote Desktop Connections'.",
    )
    feature.add_argument(
        "--avc444",
        dest="avc444",
        action="store_true",
        help="Target 'Prioritize H.264/AVC 444 graphics mode for Remote Desktop Connections'.",
    )
    feature.add_argument(
        "--wddm",
        dest="wddm",
        action="store_true",
        help="Target 'Use WDDM graphics display driver for Remote Desktop Connections'.",
    )

    trouble = parser.add_argument_group("Troubleshooting / info")
    trouble.add_argument(
        "--restart-rdp-service",
        action="store_true",
        help="Restart Remote Desktop Services (TermService). WARNING: disconnects all RDP sessions.",
    )
    trouble.add_argument(
        "--status",
        action="store_true",
        help="Show current registry values for all related policies.",
    )
    trouble.add_argument(
        "--diagnostics",
        action="store_true",
        help="Print verification and troubleshooting tips.",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be changed, but do not modify the registry.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print extra information about what the script is doing.",
    )

    return parser


def main(
    enable: bool = False,
    disable: bool = False,
    default_state: bool = False,
    gpu: bool = False,
    hw_encode: bool = False,
    avc444: bool = False,
    wddm: bool = False,
    restart_rdp_service: bool = False,
    status: bool = False,
    diagnostics: bool = False,
    dry_run: bool = False,
    verbose: bool = False,
) -> int:
    # Work out which action (if any) was requested.
    if enable:
        action: Action = "enable"
    elif disable:
        action: Action = "disable"
    elif default_state:
        action: Action = "default"
    else:
        action = None

    # Which settings are targeted?
    targets = []
    if gpu:
        targets.append("gpu")
    if hw_encode:
        targets.append("hw_encode")
    if avc444:
        targets.append("avc444")
    if wddm:
        targets.append("wddm")

    # If an action was specified but no specific setting flags,
    # treat it as "apply to all four settings".
    if action is not None and not targets:
        targets = ["gpu", "hw_encode", "avc444", "wddm"]

    # Are we changing anything?
    will_change = bool(action) or restart_rdp_service

    if not any([will_change, status, diagnostics]):
        _make_parser().print_help()
        return 0

    if will_change and not dry_run:
        if not permissions.is_admin():
            print("Error: This script must be run with administrator privileges.", file=sys.stderr)
            return 1

    # Apply requested changes for each selected setting.
    if action is not None:
        for target in targets:
            if target == "gpu":
                set_gpu_registry(action, dry_run, verbose)
            elif target == "hw_encode":
                set_hw_encoding_registry(action, dry_run, verbose)
            elif target == "avc444":
                set_avc444_registry(action, dry_run, verbose)
            elif target == "wddm":
                set_wddm_registry(action, dry_run, verbose)

            print(f"Applied action '{action}' to setting '{target}'.")

        if not status:
            print("-----------------------------")
            print("Current settings after changes:")
            print_status()

    # Info / troubleshooting
    if restart_rdp_service:
        restart_rdp_termservice_service(dry_run, verbose)
    if status:
        print_status()
    if diagnostics:
        print_diagnostics()

    if will_change and not dry_run:
        if restart_rdp_service:
            print("Changes applied and RDP service restarted.")
        else:
            print(
                "Changes applied. Restart the 'termserv' or Sign out and back in, or reboot the host, "
                "before RDP sessions pick up the new settings."
            )

    return 0


if __name__ == '__main__':
    exec_parser = _make_parser()
    args = exec_parser.parse_args()
    sys.exit(main(**vars(args)))
