#!/usr/bin/env python3
"""
clamav_installer.py

Ubuntu 24.04+ (including ARM):
- --install: installs ClamAV + optional realtime on-access scanning + optional nightly full scan
- --uninstall: removes ClamAV and all settings/files created by this installer

Examples:
  sudo python3 clamav_installer.py --install
  sudo python3 clamav_installer.py --install --nightly-scan-disable
  sudo python3 clamav_installer.py --install --realtime-disable --nightly-scan --nightly-at 03:10
  sudo python3 clamav_installer.py --uninstall
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys


VERSION: str = "1.0.0"


class Defaults:
    INSTALL: bool = False
    UNINSTALL: bool = False
    ENABLE_ALL: bool = False
    DISABLE_ALL: bool = False
    ENABLE_NIGHTLY: bool = False
    DISABLE_NIGHTLY: bool = False
    ENABLE_REALTIME: bool = False
    DISABLE_REALTIME: bool = False
    NIGHTLY_AT: str = "02:30"
    INOTIFY_WATCHES: int = 524288


def _require_root() -> None:
    if os.geteuid() != 0:
        raise PermissionError("This script must be run as root. Use: sudo ...")


def _parse_hhmm(hhmm: str) -> tuple[int, int]:
    parts = hhmm.split(":")
    if len(parts) != 2:
        raise ValueError("nightly_at must be in HH:MM format.")
    hh = int(parts[0])
    mm = int(parts[1])
    if not (0 <= hh <= 23 and 0 <= mm <= 59):
        raise ValueError("nightly_at must be a valid 24-hour time HH:MM.")
    return hh, mm


def _daily_oncalendar(hhmm: str) -> str:
    hh, mm = _parse_hhmm(hhmm)
    return f"*-*-* {hh:02d}:{mm:02d}:00"


def _run_bash(script: str) -> int:
    proc = subprocess.run(
        script,
        shell=True,
        executable="/bin/bash",
        text=True,
    )
    return proc.returncode


def _script_prelude() -> str:
    return """set -euo pipefail

export DEBIAN_FRONTEND=noninteractive

"""


def _script_install_packages() -> str:
    return """echo "[1/7] Installing ClamAV packages"
apt update
apt install -y clamav clamav-daemon

"""


def _script_enable_freshclam() -> str:
    return """echo "[2/7] Enabling signature auto-updates and priming signatures"
# Don't run a second `freshclam` instance here.
# The systemd service runs freshclam as a daemon and holds the freshclam.log lock, so a
# manual `freshclam` invocation commonly fails with "Failed to lock the log file ...".
systemctl enable --now clamav-freshclam || true
# Restart to trigger an immediate update attempt on newly-installed systems.
systemctl restart clamav-freshclam || true

"""


def _script_create_quarantine_and_log_dirs() -> str:
    return """echo "[3/7] Creating quarantine/log directories"
install -d -m 0750 -o root -g clamav /var/quarantine
install -d -m 0755 -o clamav -g clamav /var/log/clamav
"""


def _script_write_clamd_conf_realtime_enabled() -> str:
    return """echo "[4/7] Writing /etc/clamav/clamd.conf (realtime on-access enabled)"
cat >/etc/clamav/clamd.conf <<'EOF'
# Managed by clamav_installer.py

# --- Core paths ---
DatabaseDirectory /var/lib/clamav
TemporaryDirectory /tmp
LocalSocket /run/clamav/clamd.ctl
FixStaleSocket yes
PidFile /run/clamav/clamd.pid
User clamav
AllowSupplementaryGroups yes

# --- Logging ---
LogFile /var/log/clamav/clamd.log
LogTime yes
LogSyslog no

# --- Realtime On-Access scanning (fanotify) ---
# Prevention mode requires explicit include paths (not "/").
OnAccessPrevention yes

# Broad coverage including new removable storage (common mount points)
OnAccessIncludePath /home
OnAccessIncludePath /root
OnAccessIncludePath /tmp
OnAccessIncludePath /var/tmp
OnAccessIncludePath /var/mail
OnAccessIncludePath /var/spool
OnAccessIncludePath /opt
OnAccessIncludePath /srv
OnAccessIncludePath /mnt
OnAccessIncludePath /media
OnAccessIncludePath /run/media

# Safety/performance excludes
OnAccessExcludePath ^/proc
OnAccessExcludePath ^/sys
OnAccessExcludePath ^/dev
OnAccessExcludePath ^/run/(?!media)     # allow /run/media, exclude the rest of /run
OnAccessExcludePath ^/var/cache
OnAccessExcludePath ^/var/lib/apt
OnAccessExcludePath ^/var/log
OnAccessExcludePath ^/var/lib/snapd
OnAccessExcludePath ^/var/lib/flatpak
OnAccessExcludePath ^/var/lib/docker
OnAccessExcludePath ^/var/lib/containers
OnAccessExcludePath ^/snap
OnAccessExcludePath ^/lib/modules
OnAccessExcludePath ^/usr/lib/firmware
OnAccessExcludePath ^/boot/efi

OnAccessExcludeUname clamav

MaxThreads 6
OnAccessMaxThreads 6
EOF
"""


def _script_write_clamd_conf_realtime_disabled() -> str:
    return """echo "[4/7] Writing /etc/clamav/clamd.conf (realtime on-access disabled)"
cat >/etc/clamav/clamd.conf <<'EOF'
# Managed by clamav_installer.py

DatabaseDirectory /var/lib/clamav
TemporaryDirectory /tmp
LocalSocket /run/clamav/clamd.ctl
FixStaleSocket yes
PidFile /run/clamav/clamd.pid
User clamav
AllowSupplementaryGroups yes

LogFile /var/log/clamav/clamd.log
LogTime yes
LogSyslog no

# Realtime on-access scanning disabled by installer options.
EOF
"""


def _script_enable_clamd() -> str:
    return """echo "[5/7] Enabling clamd"
systemctl enable --now clamav-daemon
"""


def _script_enable_realtime_service_and_sysctl(inotify_watches: int) -> str:
    return f"""echo "[6/7] Enabling realtime on-access scanner (clamonacc) and inotify tuning"
cat >/etc/systemd/system/clamonacc.service <<'EOF'
[Unit]
Description=ClamAV On-Access Scanner (clamonacc)
After=network-online.target clamav-daemon.service
Requires=clamav-daemon.service

[Service]
Type=simple
User=root
ExecStart=/usr/sbin/clamonacc --fdpass --log=/var/log/clamav/clamonacc.log
Restart=on-failure
RestartSec=5s

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now clamonacc

cat >/etc/sysctl.d/90-custom-clamav.conf <<'EOF'
# Managed by clamav_installer.py
fs.inotify.max_user_watches={int(inotify_watches)}
EOF

sysctl --system >/dev/null || true
"""


def _script_disable_realtime_service_and_sysctl() -> str:
    return """echo "[6/7] Ensuring clamonacc is not enabled"
systemctl stop clamonacc 2>/dev/null || true
systemctl disable clamonacc 2>/dev/null || true
rm -f /etc/systemd/system/clamonacc.service
systemctl daemon-reload || true
rm -f /etc/sysctl.d/90-custom-clamav.conf
sysctl --system >/dev/null || true
"""


def _script_enable_nightly_full_scan(nightly_at: str, oncalendar: str) -> str:
    return f"""echo "[7/7] Enabling nightly full scan ({nightly_at})"
cat >/usr/local/bin/custom-clamav-fullscan <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
LOG="/var/log/clamav/fullscan-$(date +%F).log"

exec /usr/bin/clamdscan -ri / \
  --fdpass \
  --log="$LOG" \
  --move=/var/quarantine \
  --exclude-dir='^/proc' --exclude-dir='^/sys' --exclude-dir='^/dev' \
  --exclude-dir='^/run'  --exclude-dir='^/var/cache' --exclude-dir='^/var/lib/apt' \
  --exclude-dir='^/var/lib/snapd' --exclude-dir='^/var/lib/flatpak' \
  --exclude-dir='^/var/lib/docker' --exclude-dir='^/var/lib/containers' \
  --exclude-dir='^/snap' --exclude-dir='^/var/log'
EOF
chmod 0755 /usr/local/bin/custom-clamav-fullscan

cat >/etc/systemd/system/custom-clamav-fullscan.service <<'EOF'
[Unit]
Description=ClamAV Full System Scan (quarantine infected) - managed by clamav_installer.py
After=clamav-daemon.service

[Service]
Type=oneshot
ExecStart=/usr/local/bin/custom-clamav-fullscan
Nice=10
IOSchedulingClass=best-effort
IOSchedulingPriority=7
EOF

cat >/etc/systemd/system/custom-clamav-fullscan.timer <<'EOF'
[Unit]
Description=Nightly ClamAV Full Scan Timer - managed by clamav_installer.py

[Timer]
OnCalendar={oncalendar}
Persistent=true

[Install]
WantedBy=timers.target
EOF

systemctl daemon-reload
systemctl enable --now custom-clamav-fullscan.timer
"""


def _script_disable_nightly_full_scan() -> str:
    return """echo "[7/7] Nightly scan disabled; ensuring timer is not enabled"
systemctl stop custom-clamav-fullscan.timer 2>/dev/null || true
systemctl disable custom-clamav-fullscan.timer 2>/dev/null || true
rm -f /etc/systemd/system/custom-clamav-fullscan.timer
rm -f /etc/systemd/system/custom-clamav-fullscan.service
rm -f /usr/local/bin/custom-clamav-fullscan
systemctl daemon-reload || true
"""


def _script_install_checks_base() -> str:
    return """echo "DONE: ClamAV configured."
echo "Checks:"
echo "  systemctl --no-pager status clamav-daemon"
echo "  systemctl --no-pager status clamav-freshclam"
"""


def _script_install_checks_realtime() -> str:
    return """echo "  systemctl --no-pager status clamonacc"
"""


def _script_install_checks_nightly() -> str:
    return """echo "  systemctl --no-pager status custom-clamav-fullscan.timer"
"""


def _install_clamav() -> int:
    script = ""
    script += _script_prelude()
    script += _script_install_packages()
    script += _script_enable_freshclam()
    script += _script_create_quarantine_and_log_dirs()
    return _run_bash(script)


def _script_uninstall_body() -> str:
    return """echo "[1/6] Stopping/disabling managed services/timers (best effort)"
systemctl stop custom-clamav-fullscan.timer 2>/dev/null || true
systemctl disable custom-clamav-fullscan.timer 2>/dev/null || true
systemctl stop clamonacc 2>/dev/null || true
systemctl disable clamonacc 2>/dev/null || true
systemctl stop clamav-daemon 2>/dev/null || true
systemctl stop clamav-freshclam 2>/dev/null || true

echo "[2/6] Removing managed unit files, scripts, sysctl tuning"
rm -f /etc/systemd/system/custom-clamav-fullscan.timer
rm -f /etc/systemd/system/custom-clamav-fullscan.service
rm -f /usr/local/bin/custom-clamav-fullscan
rm -f /etc/systemd/system/clamonacc.service
rm -f /etc/sysctl.d/90-custom-clamav.conf
systemctl daemon-reload || true
sysctl --system >/dev/null || true

echo "[3/6] Removing quarantine and managed logs (best effort)"
rm -rf /var/quarantine
rm -f /var/log/clamav/clamonacc.log 2>/dev/null || true
rm -f /var/log/clamav/fullscan-*.log 2>/dev/null || true

echo "[4/6] Purging packages"
apt update
apt purge -y clamav clamav-daemon || true

echo "[5/6] Autoremove leftovers"
apt autoremove -y || true

echo "[6/6] Done"
"""


def _uninstall_clamav() -> int:
    script = ""
    script += _script_prelude()
    script += _script_uninstall_body()
    return _run_bash(script)


def enable_realtime_script(inotify_watches: int = Defaults.INOTIFY_WATCHES) -> int:
    script = ""
    script += _script_prelude()
    script += _script_create_quarantine_and_log_dirs()
    script += _script_write_clamd_conf_realtime_enabled()
    script += _script_enable_clamd()
    script += _script_enable_realtime_service_and_sysctl(inotify_watches)
    return _run_bash(script)


def disable_realtime_script() -> int:
    script = ""
    script += _script_prelude()
    script += _script_create_quarantine_and_log_dirs()
    script += _script_write_clamd_conf_realtime_disabled()
    script += _script_enable_clamd()
    script += _script_disable_realtime_service_and_sysctl()
    return _run_bash(script)


def enable_nightly_scan_script(nightly_at: str = Defaults.NIGHTLY_AT) -> int:
    oncalendar = _daily_oncalendar(nightly_at)

    script = ""
    script += _script_prelude()
    script += _script_create_quarantine_and_log_dirs()
    script += _script_enable_clamd()
    script += _script_enable_nightly_full_scan(nightly_at, oncalendar)
    return _run_bash(script)


def disable_nightly_scan_script() -> int:
    script = ""
    script += _script_prelude()
    script += _script_disable_nightly_full_scan()
    return _run_bash(script)


def _make_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="clamav_installer.py",
        description="Install/uninstall ClamAV with optional realtime on-access scanning and nightly full scan.",
    )
    g = p.add_mutually_exclusive_group(required=False)
    g.add_argument("--install", action="store_true", help="Install and configure ClamAV.")
    g.add_argument("--uninstall", action="store_true", help="Uninstall ClamAV and remove managed settings/files.")

    ag = p.add_mutually_exclusive_group(required=False)
    ag.add_argument(
        "--enable-all",
        action="store_true",
        default=Defaults.ENABLE_ALL,
        help="Enable all optional features (realtime on-access scanning + nightly full scan). Cannot be combined with other enable/disable flags.",
    )
    ag.add_argument(
        "--disable-all",
        action="store_true",
        default=Defaults.DISABLE_ALL,
        help="Disable all optional features (realtime on-access scanning + nightly full scan). Cannot be combined with other enable/disable flags.",
    )

    rg = p.add_mutually_exclusive_group(required=False)
    rg.add_argument(
        "--enable-realtime",
        action="store_true",
        default=Defaults.ENABLE_REALTIME,
        help="Enable realtime on-access scanning. During --install, enabled by default unless --realtime-disable is set. Without --install/--uninstall, only applied if explicitly set.",
    )
    rg.add_argument(
        "--disable-realtime",
        action="store_true",
        default=Defaults.DISABLE_REALTIME,
        help="Disable realtime on-access scanning. During --install, only disables if explicitly set. Without --install/--uninstall, only applied if explicitly set.",
    )
    p.add_argument(
        "--inotify-watches",
        type=int,
        default=Defaults.INOTIFY_WATCHES,
        help=f"fs.inotify.max_user_watches when realtime enabled. Default: {str(Defaults.INOTIFY_WATCHES)}.",
    )

    ng = p.add_mutually_exclusive_group(required=False)
    ng.add_argument(
        "--enable-nightly-scan",
        action="store_true",
        default=Defaults.ENABLE_NIGHTLY,
        help="Enable nightly full scan timer. During --install, enabled by default unless --nightly-scan-disable is set. Without --install/--uninstall, only applied if explicitly set.",
    )
    ng.add_argument(
        "--disable-nightly-scan",
        action="store_true",
        default=Defaults.DISABLE_NIGHTLY,
        help="Disable nightly full scan timer. During --install, only disables if explicitly set. Without --install/--uninstall, only applied if explicitly set.",
    )
    p.add_argument(
        "--nightly-at",
        default=Defaults.NIGHTLY_AT,
        help=f"Nightly scan time (HH:MM, 24h). Default: {Defaults.NIGHTLY_AT}.",
    )

    return p


def main(
    install: bool = Defaults.INSTALL,
    uninstall: bool = Defaults.UNINSTALL,
    enable_all: bool = Defaults.ENABLE_ALL,
    disable_all: bool = Defaults.DISABLE_ALL,
    enable_realtime: bool = Defaults.ENABLE_REALTIME,
    disable_realtime: bool = Defaults.DISABLE_REALTIME,
    inotify_watches: int = Defaults.INOTIFY_WATCHES,
    enable_nightly_scan: bool = Defaults.ENABLE_NIGHTLY,
    disable_nightly_scan: bool = Defaults.DISABLE_NIGHTLY,
    nightly_at: str = Defaults.NIGHTLY_AT,
) -> int:
    if install and uninstall:
        raise ValueError("Cannot specify both install and uninstall.")

    if enable_realtime and disable_realtime:
        raise ValueError("Cannot specify both --enable-realtime and --disable-realtime.")
    if enable_nightly_scan and disable_nightly_scan:
        raise ValueError("Cannot specify both --enable-nightly-scan and --disable-nightly-scan.")

    if enable_all and disable_all:
        raise ValueError("Cannot specify both --enable-all and --disable-all.")

    if (enable_all or disable_all) and (
        enable_realtime or disable_realtime or enable_nightly_scan or disable_nightly_scan
    ):
        raise ValueError("--enable-all/--disable-all cannot be combined with other enable/disable flags.")

    if enable_all:
        enable_realtime = True
        enable_nightly_scan = True
    elif disable_all:
        disable_realtime = True
        disable_nightly_scan = True

    _require_root()

    if install:
        rc = _install_clamav()
        if rc != 0:
            return rc

        # Print post-install checks/hints (no-op; informational only)
        checks = ""
        checks += _script_prelude()
        checks += _script_install_checks_base()
        _run_bash(checks)

    if uninstall:
        return _uninstall_clamav()

    did_any = False

    if disable_realtime:
        did_any = True
        rc = disable_realtime_script()
        if rc != 0:
            return rc
    elif enable_realtime:
        did_any = True
        rc = enable_realtime_script(inotify_watches)
        if rc != 0:
            return rc

        checks = ""
        checks += _script_prelude()
        checks += _script_install_checks_realtime()
        _run_bash(checks)

    if disable_nightly_scan:
        did_any = True
        rc = disable_nightly_scan_script()
        if rc != 0:
            return rc
    elif enable_nightly_scan:
        did_any = True
        rc = enable_nightly_scan_script(nightly_at)
        if rc != 0:
            return rc

        checks = ""
        checks += _script_prelude()
        checks += _script_install_checks_nightly()
        _run_bash(checks)

    return 0 if did_any else 2


if __name__ == "__main__":
    exec_parser = _make_parser()
    args = exec_parser.parse_args()
    exec_rc: int = main(**vars(args))
    if exec_rc == 2:
        exec_parser.print_help()
    sys.exit(exec_rc)
