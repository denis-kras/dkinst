r"""
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
import os
import ctypes
import json

from .infra import permissions, registrys

from rich.console import Console

Action = Literal["enable", "disable", "default"] | None


console = Console()


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
    r"""
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
    r"""
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
    r"""
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
    r"""
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


def check_gpu_enabled_in_current_rdp_session(verbose: bool = False) -> bool:
    r"""
    Best-effort runtime verification that the "current RDP session" is actually using GPU acceleration.

    What it does:
      - Detect current Windows Session ID.
      - Detect whether this is an RDP session (SESSIONNAME / GetSystemMetrics / GlassSessionId fallback).
      - Reads relevant RDS policy backing values from:
          HKLM\SOFTWARE\Policies\Microsoft\Windows NT\Terminal Services
      - Queries GPU performance counters (same source as Task Manager) for per-session dwm.exe via PowerShell:
          \GPU Process Memory(pid_<dwmPid>*)\Local Usage
          \GPU Engine(pid_<dwmPid>*engtype_3D)\Utilization Percentage

    Interpretation (conservative):
      - "GPU memory usage" alone is NOT treated as proof of GPU acceleration.
      - We treat *observed non-trivial 3D utilization* (max over a few samples) as the strongest signal.

    Returns:
        True  -> observed GPU 3D activity in this session.
        False -> not observed / unsupported / inconclusive.
    """

    console.print(
        "Unfortunately this method can state that GPU is working even if the setting is disabled and you start a GPU benchmark, so it is here only for a reference and is disabled.",
        style="red",
    )
    return False

    # ----------------- Local helpers (no external references) -----------------

    def _format_mb(num_bytes: float | int) -> str:
        try:
            return f"{float(num_bytes) / (1024.0 * 1024.0):.2f} MB"
        except Exception:
            return "<unavailable>"

    def _get_session_id() -> int | None:
        try:
            sess = ctypes.c_uint()
            ok = ctypes.windll.kernel32.ProcessIdToSessionId(os.getpid(), ctypes.byref(sess))
            if ok:
                return int(sess.value)
        except Exception:
            pass
        return None

    def _detect_rdp_session(session_id: int, session_name: str) -> bool:
        # Primary heuristic: environment variable set by RDP
        if session_name.upper().startswith("RDP-TCP"):
            return True

        # Fallback 1: GetSystemMetrics(SM_REMOTESESSION)
        try:
            SM_REMOTESESSION = 0x1000
            if bool(ctypes.windll.user32.GetSystemMetrics(SM_REMOTESESSION)):
                return True
        except Exception:
            pass

        # Fallback 2: GlassSessionId comparison (Windows guidance in some RDS scenarios)
        try:
            import winreg  # stdlib, Windows-only

            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SYSTEM\CurrentControlSet\Control\Terminal Server",
                0,
                winreg.KEY_READ,
            ) as k:
                glass_session_id, _ = winreg.QueryValueEx(k, "GlassSessionId")
            return int(glass_session_id) != int(session_id)
        except Exception:
            return False

    def _run_powershell(script: str) -> tuple[bool, str]:
        """
        Returns: (ok, stdout_or_error_text)
        """
        for exe in ("powershell", "pwsh"):
            try:
                result = subprocess.run(
                    [exe, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", script],
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                )
                return True, (result.stdout or "").strip()
            except FileNotFoundError:
                continue
            except subprocess.CalledProcessError as e:
                return False, (e.stdout or "").strip()
        return False, "PowerShell executable not found (powershell/pwsh)."

    def _safe_json_loads(text: str) -> dict:
        try:
            obj = json.loads(text)
            return obj if isinstance(obj, dict) else {}
        except Exception:
            return {}

    # ----------------- Main logic -----------------

    if os.name != "nt":
        print("Session GPU check is only supported on Windows.", file=sys.stderr)
        return False

    session_id = _get_session_id()
    if session_id is None:
        print("Could not determine current Windows session id.", file=sys.stderr)
        return False

    session_name = os.environ.get("SESSIONNAME", "") or ""
    in_rdp = _detect_rdp_session(session_id, session_name)

    if verbose:
        print(f"SESSIONNAME: {session_name!r}")
        print(f"Session ID: {session_id}")
        print(f"Remote session detected: {in_rdp}")

    # Read configured policy values (intent/config).
    gpu_policy = registrys.get_policy_dword("bEnumerateHWBeforeSW", TERMINAL_SERVICES_KEY, "HKLM")
    wddm_policy = registrys.get_policy_dword("fEnableWddmDriver", TERMINAL_SERVICES_KEY, "HKLM")

    # PowerShell script: find dwm.exe in this session, then query GPU counters for that PID.
    # IMPORTANT: counter paths must start with a SINGLE "\" (local machine). "\\..." is a remote machine path.
    ps_template = r"""
$ErrorActionPreference = 'Stop'
$sess = __SESSION_ID__

$dwm = Get-Process dwm -ErrorAction SilentlyContinue | Where-Object { $_.SessionId -eq $sess } | Select-Object -First 1
if (-not $dwm) {
  @{ ok=$false; reason="No dwm.exe found for current session"; sessionId=$sess } | ConvertTo-Json -Compress
  exit 0
}

$dwmPid = $dwm.Id

$memBytes = $null
$memInstances = 0
$memError = $null
try {
  $memSamples = (Get-Counter "\GPU Process Memory(pid_$dwmPid*)\Local Usage" -ErrorAction Stop).CounterSamples
  $memInstances = @($memSamples).Count
  if ($memInstances -gt 0) {
    # Use MAX across instances to avoid double-counting.
    $memBytes = ($memSamples | Measure-Object -Property CookedValue -Maximum).Maximum
  }
} catch {
  $memError = $_.Exception.Message
}

$engMaxPct = $null
$engInstances = 0
$engError = $null

# Sample multiple times to reduce false 0.00% on an idle instant.
$sampleIntervalSec = 1
$maxSamples = 3

try {
  $engSets = Get-Counter "\GPU Engine(pid_$dwmPid*engtype_3D)\Utilization Percentage" -SampleInterval $sampleIntervalSec -MaxSamples $maxSamples -ErrorAction Stop
  $engSamples = $engSets.CounterSamples
  $engInstances = @($engSamples).Count
  if ($engInstances -gt 0) {
    $engMaxPct = ($engSamples | Measure-Object -Property CookedValue -Maximum).Maximum
  }
} catch {
  $engError = $_.Exception.Message
}

@{
  ok=$true;
  sessionId=$sess;
  dwmPid=$dwmPid;
  gpuMemLocalBytes=$memBytes;
  gpuMemCounterInstances=$memInstances;
  gpu3dUtilMaxPct=$engMaxPct;
  gpu3dCounterInstances=$engInstances;
  sampleIntervalSec=$sampleIntervalSec;
  maxSamples=$maxSamples;
  memError=$memError;
  engError=$engError;
} | ConvertTo-Json -Compress
""".strip()

    ps_script = ps_template.replace("__SESSION_ID__", str(session_id))
    ok, ps_out = _run_powershell(ps_script)
    if not ok:
        print("Failed to run PowerShell/Get-Counter for session GPU check.", file=sys.stderr)
        if ps_out:
            print(ps_out, file=sys.stderr)
        return False

    data = _safe_json_loads(ps_out)
    if not data:
        print("PowerShell returned no JSON output for session GPU check.", file=sys.stderr)
        if ps_out and verbose:
            print(ps_out, file=sys.stderr)
        return False

    if not data.get("ok", False):
        print(f"Session GPU check failed: {data.get('reason', 'unknown error')}", file=sys.stderr)
        return False

    dwm_pid = data.get("dwmPid")
    mem_bytes = data.get("gpuMemLocalBytes")
    mem_instances = int(data.get("gpuMemCounterInstances") or 0)
    eng_instances = int(data.get("gpu3dCounterInstances") or 0)
    eng_max_pct = data.get("gpu3dUtilMaxPct")
    sample_interval = data.get("sampleIntervalSec")
    max_samples = data.get("maxSamples")

    # Conservative verdict:
    # - Memory allocation alone is NOT used as proof.
    # - Require non-trivial 3D utilization.
    activity_threshold_pct = 0.10
    activity_detected = isinstance(eng_max_pct, (int, float)) and float(eng_max_pct) > activity_threshold_pct
    enabled = bool(activity_detected)

    print("Session GPU verification (best-effort):")
    print(f"  Remote session detected: {in_rdp} (SESSIONNAME={session_name!r})")
    print(f"  Session ID: {session_id}")
    print(f"  Policy bEnumerateHWBeforeSW (GPU adapter): {gpu_policy if gpu_policy is not None else '<not set>'}")
    print(f"  Policy fEnableWddmDriver (WDDM): {wddm_policy if wddm_policy is not None else '<not set>'}")
    print(f"  DWM PID (this session): {dwm_pid if dwm_pid is not None else '<unavailable>'}")

    if mem_instances > 0 and mem_bytes is not None:
        print(f"  DWM GPU process memory (Local Usage): {_format_mb(mem_bytes)}")
    else:
        print("  DWM GPU process memory (Local Usage): <unavailable>")
        if data.get("memError") and verbose:
            print(f"    memError: {data.get('memError')}")

    if eng_instances > 0 and eng_max_pct is not None:
        print(
            f"  DWM GPU 3D engine utilization (max over {max_samples} samples @ {sample_interval}s): "
            f"{float(eng_max_pct):.2f}%"
        )
    else:
        print("  DWM GPU 3D engine utilization: <unavailable>")
        if data.get("engError") and verbose:
            print(f"    engError: {data.get('engError')}")

    if not enabled:
        if gpu_policy == 1:
            print(
                "  Note: policy indicates GPU adapters are enabled, but no 3D activity was observed. "
                "This can happen if the session is idle; run a GPU-heavy workload and re-check."
            )
        elif gpu_policy == 0:
            print(
                "  Note: policy indicates GPU adapters are disabled. Some GPU memory usage may still appear for DWM; "
                "memory alone is not treated as proof of GPU acceleration."
            )

    print(
        f"  Verdict: "
        f"{'GPU rendering appears ENABLED in this session' if enabled else 'GPU rendering does NOT appear enabled in this session'}"
    )
    return enabled


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
        "-tcg", "--check-session-gpu",
        action = "store_true",
        help = "Best-effort runtime check: verify the CURRENT session is using the GPU (via DWM GPU counters).",
    )
    trouble.add_argument(
        "-ts", "--status",
        action="store_true",
        help="Show current registry values for all related policies.",
    )
    trouble.add_argument(
        "-td", "--diagnostics",
        action="store_true",
        help="Print verification and troubleshooting tips.",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be changed, but do not modify the registry.",
    )
    parser.add_argument(
        "-v", "--verbose",
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
    check_session_gpu: bool = False,
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

    if not any([will_change, status, diagnostics, check_session_gpu]):
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
    if check_session_gpu:
        check_gpu_enabled_in_current_rdp_session(verbose=verbose)
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
