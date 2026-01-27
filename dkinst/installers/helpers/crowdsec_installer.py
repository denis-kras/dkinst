#!/usr/bin/env python3
"""
crowdsec_installer.py

Ubuntu 24.04+ (including ARM):
- --install: installs CrowdSec + optional UFW logging (installs UFW if missing) + optional bouncer + optional acquis
- --uninstall: removes CrowdSec and settings/files created by this installer (does not remove UFW)

Examples:
  sudo python3 crowdsec_installer.py --install
  sudo python3 crowdsec_installer.py --install --bouncer iptables --no-ufw-logging
  sudo python3 crowdsec_installer.py --uninstall
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys


VERSION: str = "1.0.0"


DEFAULT_BOUNCER_BACKEND = "nftables"
DEFAULT_COLLECTIONS = ["crowdsecurity/linux", "crowdsecurity/sshd", "crowdsecurity/iptables"]


class Defaults:
    INSTALL: bool = False
    UNINSTALL: bool = False
    ENABLE_ALL: bool = False
    DISABLE_ALL: bool = False
    ENABLE_BOUNCER: str | None = None
    DISABLE_BOUNCER: bool = False
    ENABLE_COLLECTIONS: list[str] | None = None
    DISABLE_COLLECTIONS: bool = False
    ENABLE_UFW_LOGGING: bool = False
    DISABLE_UFW_LOGGING: bool = False
    ENABLE_JOURNALD_LOGGING: bool = False
    DISABLE_JOURNALD_LOGGING: bool = False


def _require_root() -> None:
    if os.geteuid() != 0:
        raise PermissionError("This script must be run as root. Use: sudo ...")


def _run_bash(script: str) -> int:
    proc = subprocess.run(
        script,
        shell=True,
        executable="/bin/bash",
        text=True,
    )
    return proc.returncode


def _bash_preamble() -> str:
    return """set -euo pipefail

export DEBIAN_FRONTEND=noninteractive

"""


def _bash_prereqs() -> str:
    return """echo "[1/7] Installing prerequisites"
apt update
apt install -y curl ca-certificates gnupg
"""


def _bash_apt_update() -> str:
    return """apt update
"""


def _bash_ensure_ufw() -> str:
    return """echo "Ensuring UFW is installed (not enabling firewall)"
if ! command -v ufw >/dev/null 2>&1; then
  apt install -y ufw
  echo "UFW installed (not enabled). If you use SSH, do this before enabling:"
  echo "  sudo ufw allow OpenSSH && sudo ufw enable"
fi
"""


def _bash_repo_bootstrap() -> str:
    return """echo "[3/7] Installing CrowdSec repository/bootstrap"
curl -s https://install.crowdsec.net | sh

"""


def _bash_install_engine() -> str:
    return """echo "[4/7] Installing CrowdSec engine"
apt update
apt install -y crowdsec
systemctl enable --now crowdsec || true
"""


def _bash_bouncer_nftables() -> str:
    return """echo "[5/7] Installing nftables bouncer"
apt install -y crowdsec-firewall-bouncer-nftables
systemctl enable --now crowdsec-firewall-bouncer || true
"""


def _bash_bouncer_iptables() -> str:
    return """echo "[5/7] Installing iptables bouncer"
apt install -y crowdsec-firewall-bouncer-iptables
systemctl enable --now crowdsec-firewall-bouncer || true
"""


def _bash_bouncer_disable_all() -> str:
    return """echo "Disabling ALL CrowdSec bouncers (best effort)"
# Stop the common firewall bouncer service (ignore if missing)
systemctl stop crowdsec-firewall-bouncer 2>/dev/null || true
systemctl disable crowdsec-firewall-bouncer 2>/dev/null || true

# Remove common firewall bouncer packages (ignore if not installed)
apt purge -y crowdsec-firewall-bouncer-nftables crowdsec-firewall-bouncer-iptables 2>/dev/null || true
apt autoremove -y || true

# Remove local bouncer data (best effort)
rm -rf /var/lib/crowdsec-firewall-bouncer 2>/dev/null || true

# Disable all bouncers at the CrowdSec level (API keys) (best effort)
if command -v cscli >/dev/null 2>&1; then
  python3 - <<'PY' || true
import json
import subprocess
import sys

def _safe_json(cmd: list[str]) -> list[dict]:
    try:
        out = subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL)
        data = json.loads(out)
        return data if isinstance(data, list) else []
    except Exception:
        return []

bouncers = _safe_json(["cscli", "bouncers", "list", "-o", "json"])
names: list[str] = []
for b in bouncers:
    if isinstance(b, dict):
        name = b.get("name") or b.get("Name")
        if name:
            names.append(str(name))

for name in names:
    try:
        subprocess.run(["cscli", "bouncers", "delete", name], input="y\n", text=True, check=False)
    except Exception:
        pass
PY
fi
"""


def _bash_skip_bouncer() -> str:
    return """echo "[5/7] Skipping bouncer install (per options)"
"""


def _bash_collections(cols: str) -> str:
    return f"""echo "[6/7] Installing collections (best effort)"
cscli hub update || true
for c in {cols}; do
  cscli collections install "$c" || true
done

"""


def _bash_collections_disable_all() -> str:
    return """echo "Disabling ALL CrowdSec collections (best effort)"
if command -v cscli >/dev/null 2>&1; then
  python3 - <<'PY' || true
import json
import subprocess
import sys

def _safe_json(cmd: list[str]) -> list[dict]:
    try:
        out = subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL)
        data = json.loads(out)
        return data if isinstance(data, list) else []
    except Exception:
        return []

cols = _safe_json(["cscli", "collections", "list", "-o", "json"])
names: list[str] = []
for c in cols:
    if isinstance(c, dict):
        name = c.get("name") or c.get("Name")
        if name:
            names.append(str(name))

for name in names:
    try:
        subprocess.run(["cscli", "collections", "remove", name], input="y\n", text=True, check=False)
    except Exception:
        pass
PY
fi
"""


def _bash_acquis_header() -> str:
    return """echo "[7/7] Configuring acquisitions (journald)"
install -d -m 0755 /etc/crowdsec/acquis.d
"""


def _bash_acquis_sshd_enable() -> str:
    return """cat >/etc/crowdsec/acquis.d/10-sshd-journald.yaml <<'EOF'
# Managed by crowdsec_installer.py
source: journalctl
journalctl_filter:
  - "_SYSTEMD_UNIT=ssh.service"
labels:
  type: journald
EOF
"""


def _bash_acquis_sshd_disable() -> str:
    return """rm -f /etc/crowdsec/acquis.d/10-sshd-journald.yaml
"""


def _bash_acquis_kernel_enable() -> str:
    return """cat >/etc/crowdsec/acquis.d/20-kernel-journald.yaml <<'EOF'
# Managed by crowdsec_installer.py
source: journalctl
journalctl_filter:
  - "-k"
labels:
  type: syslog
EOF
"""


def _bash_acquis_kernel_disable() -> str:
    return """rm -f /etc/crowdsec/acquis.d/20-kernel-journald.yaml
"""


def _bash_ufw_logging_enable() -> str:
    return _bash_ensure_ufw() + """
echo "Enabling UFW logging (safe even if UFW is not enabled)..."
if command -v ufw >/dev/null 2>&1; then
  ufw logging on || true
fi
"""


def _bash_ufw_logging_disable() -> str:
    return """echo "Disabling UFW logging (best effort)..."
if command -v ufw >/dev/null 2>&1; then
  ufw logging off || true
fi
"""


def _bash_ufw_logging_skip() -> str:
    return """echo "Skipping UFW logging (per options)"
"""


def _bash_restart_status_done() -> str:
    return """echo "Restarting CrowdSec..."
systemctl restart crowdsec || true

echo "Status (best effort):"
cscli bouncers list || true
cscli metrics || true

echo "DONE: CrowdSec configured."
"""


def _bash_uninstall_body() -> str:
    return """echo "[1/6] Stopping/disabling services (best effort)"
systemctl stop crowdsec-firewall-bouncer 2>/dev/null || true
systemctl disable crowdsec-firewall-bouncer 2>/dev/null || true
systemctl stop crowdsec 2>/dev/null || true
systemctl disable crowdsec 2>/dev/null || true

echo "[2/6] Purging packages"
apt update
apt purge -y crowdsec crowdsec-firewall-bouncer-nftables crowdsec-firewall-bouncer-iptables || true
apt autoremove -y || true

echo "[3/6] Removing CrowdSec config/data/logs (best effort)"
rm -rf /etc/crowdsec
rm -rf /var/lib/crowdsec
rm -rf /var/log/crowdsec
rm -rf /var/lib/crowdsec-firewall-bouncer 2>/dev/null || true

echo "[4/6] Removing CrowdSec apt repo files and keys (best effort)"
rm -f /etc/apt/sources.list.d/*crowdsec*.list
rm -f /etc/apt/keyrings/*crowdsec*.gpg
rm -f /etc/apt/trusted.gpg.d/*crowdsec*.gpg

echo "[5/6] Updating apt indexes"
apt update || true

echo "[6/6] Done (UFW not removed)."
"""


def _build_install_script(
    ufw_logging: bool | None,
    bouncer: str | None,
    disable_bouncer: bool,
    collections: list[str] | None,
    disable_collections: bool,
    journald_logging: bool | None,
) -> str:
    script = ""
    script += _bash_preamble()
    script += _bash_prereqs()

    script += _bash_repo_bootstrap()
    script += _bash_install_engine()

    if disable_bouncer:
        script += _bash_bouncer_disable_all()
    elif bouncer == "nftables":
        script += _bash_bouncer_nftables()
    elif bouncer == "iptables":
        script += _bash_bouncer_iptables()
    else:
        script += _bash_skip_bouncer()

    if disable_collections:
        script += _bash_collections_disable_all()
    elif collections is not None:
        cols = " ".join(collections)
        script += _bash_collections(cols)
    else:
        script += """echo "[6/7] Skipping collections install (not requested)"
"""

    if journald_logging is not None:
        script += _bash_acquis_header()
        if journald_logging:
            script += _bash_acquis_sshd_enable()
            script += _bash_acquis_kernel_enable()
        else:
            script += _bash_acquis_sshd_disable()
            script += _bash_acquis_kernel_disable()

    if ufw_logging is True:
        script += _bash_ufw_logging_enable()
    elif ufw_logging is False:
        script += _bash_ufw_logging_disable()
    else:
        script += _bash_ufw_logging_skip()

    script += _bash_restart_status_done()
    return script


def _build_uninstall_script() -> str:
    script = ""
    script += _bash_preamble()
    script += _bash_uninstall_body()
    return script


def _build_actions_script(
    ufw_logging: bool | None,
    bouncer: str | None,
    disable_bouncer: bool,
    collections: list[str] | None,
    disable_collections: bool,
    journald_logging: bool | None,
) -> str:
    script = ""
    script += _bash_preamble()

    apt_update_needed = False
    if disable_bouncer or (bouncer is not None):
        apt_update_needed = True
    if ufw_logging is True:
        apt_update_needed = True

    if apt_update_needed:
        script += _bash_apt_update()

    if disable_bouncer:
        script += _bash_bouncer_disable_all()
    elif bouncer is not None:
        if bouncer == "nftables":
            script += _bash_bouncer_nftables()
        elif bouncer == "iptables":
            script += _bash_bouncer_iptables()
        else:
            script += _bash_skip_bouncer()

    if disable_collections:
        script += _bash_collections_disable_all()
    elif collections is not None:
        cols = " ".join(collections)
        script += _bash_collections(cols)

    if journald_logging is not None:
        script += _bash_acquis_header()
        if journald_logging:
            script += _bash_acquis_sshd_enable()
            script += _bash_acquis_kernel_enable()
        else:
            script += _bash_acquis_sshd_disable()
            script += _bash_acquis_kernel_disable()

    if ufw_logging is True:
        script += _bash_ufw_logging_enable()
    elif ufw_logging is False:
        script += _bash_ufw_logging_disable()

    if any([
        disable_bouncer,
        bouncer is not None,
        disable_collections,
        collections is not None,
        journald_logging is not None,
    ]):
        script += _bash_restart_status_done()

    return script


def _validate_cli_args(
    install: bool,
    uninstall: bool,
    enable_all: bool,
    disable_all: bool,
    enable_bouncer: str | None,
    disable_bouncer: bool,
    enable_collections: list[str] | None,
    disable_collections: bool,
    enable_ufw_logging: bool,
    disable_ufw_logging: bool,
    enable_journald_logging: bool,
    disable_journald_logging: bool,
) -> None:
    if install and uninstall:
        raise ValueError("Choose only one: --install or --uninstall.")

    if enable_all and disable_all:
        raise ValueError("Choose only one: --enable-all or --disable-all.")

    if enable_bouncer is not None and disable_bouncer:
        raise ValueError("Do not combine --enable-bouncer with --disable-bouncer.")

    if enable_collections is not None and disable_collections:
        raise ValueError("Do not combine --enable-collections with --disable-collections.")

    if enable_ufw_logging and disable_ufw_logging:
        raise ValueError("Do not combine --enable-ufw-logging with --disable-ufw-logging.")

    if enable_journald_logging and disable_journald_logging:
        raise ValueError("Do not combine --enable-journald-logging with --disable-journald-logging.")

    per_feature_flags_present = any(
        [
            enable_bouncer is not None,
            disable_bouncer,
            enable_collections is not None,
            disable_collections,
            enable_ufw_logging,
            disable_ufw_logging,
            enable_journald_logging,
            disable_journald_logging,
        ]
    )

    if (enable_all or disable_all) and per_feature_flags_present:
        raise ValueError(
            "--enable-all/--disable-all cannot be combined with per-feature enable/disable flags."
        )

    if uninstall and (enable_all or disable_all or per_feature_flags_present):
        raise ValueError("--uninstall cannot be combined with any feature enable/disable flags.")


def _resolve_feature_intents(
    enable_all: bool,
    disable_all: bool,
    enable_bouncer: str | None,
    disable_bouncer: bool,
    enable_collections: list[str] | None,
    disable_collections: bool,
    enable_ufw_logging: bool,
    disable_ufw_logging: bool,
    enable_journald_logging: bool,
    disable_journald_logging: bool,
) -> tuple[str | None, bool, list[str] | None, bool, bool | None, bool | None]:
    # Returns: (bouncer_backend, disable_bouncer, collections_to_install, disable_collections, ufw_logging, journald_logging)
    if enable_all:
        return (
            DEFAULT_BOUNCER_BACKEND,
            False,
            DEFAULT_COLLECTIONS,
            False,
            True,
            True,
        )

    if disable_all:
        return (None, True, None, True, False, False)

    bouncer_backend = None if disable_bouncer else enable_bouncer

    collections_to_install: list[str] | None = None
    if not disable_collections and enable_collections is not None:
        collections_to_install = enable_collections if len(enable_collections) > 0 else DEFAULT_COLLECTIONS

    ufw_logging = True if enable_ufw_logging else False if disable_ufw_logging else None
    journald_logging = True if enable_journald_logging else False if disable_journald_logging else None

    return (
        bouncer_backend,
        disable_bouncer,
        collections_to_install,
        disable_collections,
        ufw_logging,
        journald_logging,
    )


def _install_crowdsec_core() -> int:
    script = ""
    script += _bash_preamble()
    script += _bash_prereqs()
    script += _bash_repo_bootstrap()
    script += _bash_install_engine()
    return _run_bash(script)


def _uninstall_crowdsec() -> int:
    return _run_bash(_build_uninstall_script())


def _enable_bouncer(backend: str) -> int:
    if backend == "nftables":
        snippet = _bash_bouncer_nftables()
    elif backend == "iptables":
        snippet = _bash_bouncer_iptables()
    else:
        raise ValueError(f"Unknown bouncer backend: {backend}")

    script = ""
    script += _bash_preamble()
    script += _bash_apt_update()
    script += snippet
    return _run_bash(script)


def _disable_bouncers() -> int:
    return _run_bash(_bash_preamble() + _bash_bouncer_disable_all())


def _enable_collections(collections: list[str]) -> int:
    cols = " ".join(collections)
    return _run_bash(_bash_preamble() + _bash_collections(cols))


def _disable_collections() -> int:
    return _run_bash(_bash_preamble() + _bash_collections_disable_all())


def _set_journald_logging(enabled: bool) -> int:
    snippet = _bash_acquis_header()
    if enabled:
        snippet += _bash_acquis_sshd_enable()
        snippet += _bash_acquis_kernel_enable()
    else:
        snippet += _bash_acquis_sshd_disable()
        snippet += _bash_acquis_kernel_disable()

    return _run_bash(_bash_preamble() + snippet)


def _set_ufw_logging(enabled: bool) -> int:
    if enabled:
        script = ""
        script += _bash_preamble()
        script += _bash_apt_update()
        script += _bash_ufw_logging_enable()
        return _run_bash(script)

    return _run_bash(_bash_preamble() + _bash_ufw_logging_disable())


def _restart_and_status() -> int:
    return _run_bash(_bash_preamble() + _bash_restart_status_done())


def _apply_feature_intents(
    bouncer_backend: str | None,
    disable_bouncer: bool,
    collections_to_install: list[str] | None,
    disable_collections: bool,
    ufw_logging: bool | None,
    journald_logging: bool | None,
) -> int:
    if disable_bouncer:
        rc = _disable_bouncers()
        if rc != 0:
            return rc
    elif bouncer_backend is not None:
        rc = _enable_bouncer(bouncer_backend)
        if rc != 0:
            return rc

    if disable_collections:
        rc = _disable_collections()
        if rc != 0:
            return rc
    elif collections_to_install is not None:
        rc = _enable_collections(collections_to_install)
        if rc != 0:
            return rc

    if journald_logging is not None:
        rc = _set_journald_logging(journald_logging)
        if rc != 0:
            return rc

    if ufw_logging is not None:
        rc = _set_ufw_logging(ufw_logging)
        if rc != 0:
            return rc

    return 0


def _make_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="crowdsec_installer.py",
        description="Install/uninstall CrowdSec with optional features.",
    )
    g = p.add_mutually_exclusive_group(required=False)
    g.add_argument("--install", action="store_true", help="Install and configure CrowdSec.")
    g.add_argument("--uninstall", action="store_true", help="Uninstall CrowdSec and remove managed settings/files.")

    all_g = p.add_mutually_exclusive_group(required=False)
    all_g.add_argument(
        "--enable-all",
        action="store_true",
        default=Defaults.ENABLE_ALL,
        help="Enable all optional features (bouncer, collections, journald logging, UFW logging).",
    )
    all_g.add_argument(
        "--disable-all",
        action="store_true",
        default=Defaults.DISABLE_ALL,
        help="Disable all optional features (bouncers, collections, journald logging, UFW logging).",
    )

    bouncer_g = p.add_mutually_exclusive_group(required=False)
    bouncer_g.add_argument(
        "--enable-bouncer",
        nargs="?",
        const=DEFAULT_BOUNCER_BACKEND,
        choices=["nftables", "iptables"],
        default=Defaults.ENABLE_BOUNCER,
        help="Firewall bouncer backend to install. If omitted, no bouncer is installed/used.",
    )
    bouncer_g.add_argument(
        "--disable-bouncer",
        action="store_true",
        default=Defaults.DISABLE_BOUNCER,
        help="Disable all CrowdSec bouncers (best effort).",
    )

    collections_g = p.add_mutually_exclusive_group(required=False)
    collections_g.add_argument(
        "--enable-collections",
        nargs="*",
        default=Defaults.ENABLE_COLLECTIONS,
        help="CrowdSec collections to install. If provided with no values, installs the defaults.",
    )
    collections_g.add_argument(
        "--disable-collections",
        action="store_true",
        default=Defaults.DISABLE_COLLECTIONS,
        help="Disable all CrowdSec collections (best effort).",
    )

    ufw_g = p.add_mutually_exclusive_group(required=False)
    ufw_g.add_argument(
        "--enable-ufw-logging",
        action="store_true",
        default=Defaults.ENABLE_UFW_LOGGING,
        help="Enable UFW logging (installs UFW if missing).",
    )
    ufw_g.add_argument(
        "--disable-ufw-logging",
        action="store_true",
        default=Defaults.DISABLE_UFW_LOGGING,
        help="Disable UFW logging.",
    )

    journald_g = p.add_mutually_exclusive_group(required=False)
    journald_g.add_argument(
        "--enable-journald-logging",
        action="store_true",
        default=Defaults.ENABLE_JOURNALD_LOGGING,
        help="Enable journald acquisitions (SSHD + kernel).",
    )
    journald_g.add_argument(
        "--disable-journald-logging",
        action="store_true",
        default=Defaults.DISABLE_JOURNALD_LOGGING,
        help="Disable journald acquisitions (SSHD + kernel).",
    )

    return p


def main(
    install: bool = Defaults.INSTALL,
    uninstall: bool = Defaults.UNINSTALL,
    enable_all: bool = Defaults.ENABLE_ALL,
    disable_all: bool = Defaults.DISABLE_ALL,
    enable_bouncer: str | None = Defaults.ENABLE_BOUNCER,
    disable_bouncer: bool = Defaults.DISABLE_BOUNCER,
    enable_collections: list[str] | None = Defaults.ENABLE_COLLECTIONS,
    disable_collections: bool = Defaults.DISABLE_COLLECTIONS,
    enable_ufw_logging: bool = Defaults.ENABLE_UFW_LOGGING,
    disable_ufw_logging: bool = Defaults.DISABLE_UFW_LOGGING,
    enable_journald_logging: bool = Defaults.ENABLE_JOURNALD_LOGGING,
    disable_journald_logging: bool = Defaults.DISABLE_JOURNALD_LOGGING,
) -> int:
    try:
        _validate_cli_args(
            install=install,
            uninstall=uninstall,
            enable_all=enable_all,
            disable_all=disable_all,
            enable_bouncer=enable_bouncer,
            disable_bouncer=disable_bouncer,
            enable_collections=enable_collections,
            disable_collections=disable_collections,
            enable_ufw_logging=enable_ufw_logging,
            disable_ufw_logging=disable_ufw_logging,
            enable_journald_logging=enable_journald_logging,
            disable_journald_logging=disable_journald_logging,
        )
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2

    _require_root()

    (
        bouncer_backend,
        disable_bouncer_eff,
        collections_to_install,
        disable_collections_eff,
        ufw_logging,
        journald_logging,
    ) = _resolve_feature_intents(
        enable_all=enable_all,
        disable_all=disable_all,
        enable_bouncer=enable_bouncer,
        disable_bouncer=disable_bouncer,
        enable_collections=enable_collections,
        disable_collections=disable_collections,
        enable_ufw_logging=enable_ufw_logging,
        disable_ufw_logging=disable_ufw_logging,
        enable_journald_logging=enable_journald_logging,
        disable_journald_logging=disable_journald_logging,
    )

    if install:
        rc = _install_crowdsec_core()
        if rc != 0:
            return rc

        rc = _apply_feature_intents(
            bouncer_backend=bouncer_backend,
            disable_bouncer=disable_bouncer_eff,
            collections_to_install=collections_to_install,
            disable_collections=disable_collections_eff,
            ufw_logging=ufw_logging,
            journald_logging=journald_logging,
        )
        if rc != 0:
            return rc

        return _restart_and_status()

    if uninstall:
        return _uninstall_crowdsec()

    actions_requested = any(
        [
            disable_bouncer_eff,
            bouncer_backend is not None,
            disable_collections_eff,
            collections_to_install is not None,
            ufw_logging is not None,
            journald_logging is not None,
        ]
    )
    if not actions_requested:
        return 2

    rc = _apply_feature_intents(
        bouncer_backend=bouncer_backend,
        disable_bouncer=disable_bouncer_eff,
        collections_to_install=collections_to_install,
        disable_collections=disable_collections_eff,
        ufw_logging=ufw_logging,
        journald_logging=journald_logging,
    )
    if rc != 0:
        return rc

    return _restart_and_status()


if __name__ == "__main__":
    exec_parser = _make_parser()
    args = exec_parser.parse_args()
    sys.exit(main(**vars(args)))
