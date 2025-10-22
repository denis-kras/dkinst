import os
import ctypes
from typing import Literal

if os.name == "nt":
    import winreg


def _broadcast_env_change(_ctypes):
    HWND_BROADCAST = 0xFFFF
    WM_SETTINGCHANGE = 0x001A
    SMTO_ABORTIFHUNG = 0x0002
    _ctypes.windll.user32.SendMessageTimeoutW(
        HWND_BROADCAST, WM_SETTINGCHANGE, 0, "Environment",
        SMTO_ABORTIFHUNG, 5000, _ctypes.byref(_ctypes.c_ulong())
    )


def ensure_exe_dir_in_path(
    exe_path: str,
    scope: Literal["user", "machine"] = "user",                # 'user' (no admin) or 'machine' (admin required)
    include_windows_dirs: bool = False, # protect C:\Windows* by default
    position: Literal["front", "end"] = "end",              # 'end' or 'front' (where to put the new dir)
    require_existence: bool = True      # verify the exe actually exists
):
    """
    Ensure PATH has exactly one directory providing the given executable:
      - If any PATH entry currently provides an exe with the same filename, replace those entries with `dir(exe_path)`
      - Otherwise, append (or prepend) the new directory

    :param exe_path: Full path to the executable to ensure on PATH (e.g. C:\vcpkg\installed\x64-windows\tools\tesseract\tesseract.exe).
    :param scope: 'user' (no admin) or 'machine' (admin required).
    :param include_windows_dirs: Whether to allow replacing PATH entries under C:\Windows* (not recommended).
    :param position: 'end' or 'front' (where to put the new dir if adding).
    :param require_existence: True, raise an exception if exe_path does not exist.
    :return: Returns a dict with details: {'action', 'replaced_dirs', 'new_dir', 'scope'}

    -----------------------------

    Example usage:
    result = ensure_exe_dir_on_path(
        r"C:\vcpkg\installed\x64-windows\tools\tesseract\tesseract.exe",
        scope="user",                # or "machine" (admin)
        include_windows_dirs=False,  # safety: don't touch C:\Windows* by default
        position="end"               # or "front" to prioritize this version
    )
    print(result)

    """

    # ---------- inner helpers (no outer vars captured) ----------
    def _norm_dir(path_str: str, _os):
        p = (path_str or "").strip().strip('"').replace("/", "\\")
        while p.endswith("\\"):
            p = p[:-1]
        return _os.path.normcase(_os.path.normpath(p))

    def _comp_norm(path_str: str, _os):
        return _norm_dir(_os.path.expandvars(path_str or ""), _os)

    def _is_windows_rooted(path_str: str, _os):
        expanded_internal = _os.path.expandvars(path_str or "").replace("/", "\\").rstrip("\\").lower()
        roots = []
        for env in ("SystemRoot", "windir"):
            v = _os.environ.get(env)
            if v:
                roots.append(v.replace("/", "\\").rstrip("\\").lower())
        return any(expanded_internal == r or expanded_internal.startswith(r + "\\") for r in roots)

    def _read_path(_scope: str, _winreg):
        if _scope == "user":
            root, subkey = _winreg.HKEY_CURRENT_USER, r"Environment"
        else:
            root, subkey = _winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"
        try:
            with _winreg.OpenKey(root, subkey, 0, _winreg.KEY_READ) as k:
                val, reg_type = _winreg.QueryValueEx(k, "Path")
        except FileNotFoundError:
            val, reg_type = "", _winreg.REG_EXPAND_SZ
        return val, reg_type, (root, subkey)

    def _write_path(root_subkey, new_val_internal: str, reg_type: int, _winreg):
        root, subkey = root_subkey
        with _winreg.OpenKey(root, subkey, 0, _winreg.KEY_SET_VALUE) as k:
            _winreg.SetValueEx(k, "Path", 0, reg_type or _winreg.REG_EXPAND_SZ, new_val_internal)

    def _dir_contains_exe(dir_candidate: str, exe_name_internal: str, _os):
        raw_internal = (dir_candidate or "").strip().strip('"')
        exp = _os.path.expandvars(raw_internal)
        return _os.path.isfile(_os.path.join(exp, exe_name_internal))


    # ---------- validate & derive ----------
    if position not in ("end", "front"):
        raise ValueError("position must be 'end' or 'front'")
    if scope not in ("user", "machine"):
        raise ValueError("scope must be 'user' or 'machine'")
    if not exe_path or not isinstance(exe_path, str):
        raise ValueError("exe_path must be a non-empty string")

    raw = exe_path.strip().strip('"')
    expanded = os.path.expandvars(raw)
    norm_exe = os.path.normpath(expanded)

    if not norm_exe.lower().endswith(".exe"):
        raise ValueError("exe_path must point to a .exe file")
    if require_existence and not os.path.isfile(norm_exe):
        raise FileNotFoundError(f"Executable not found: {norm_exe}")

    new_dir = os.path.dirname(norm_exe)
    exe_name = os.path.basename(norm_exe)
    new_dir_norm = _norm_dir(new_dir, os)

    # ---------- persisted PATH (registry) ----------
    cur_path, regtype, handle = _read_path(scope, winreg)
    parts = [p for p in cur_path.split(";") if p]

    out_parts = []
    seen_dirs = set()
    replaced_dirs = []
    changed = False

    for p in parts:
        comp = _comp_norm(p, os)
        if comp in seen_dirs:
            changed = True
            continue
        if _dir_contains_exe(p, exe_name, os):
            if include_windows_dirs or not _is_windows_rooted(p, os):
                replaced_dirs.append(p)
                changed = True
                continue  # drop old provider
        out_parts.append(p)
        seen_dirs.add(comp)

    if new_dir_norm not in seen_dirs:
        if position == "front":
            out_parts = [new_dir] + out_parts
        else:
            out_parts.append(new_dir)
        changed = True

    new_val = ";".join(out_parts).strip(";")
    if changed:
        _write_path(handle, new_val, regtype, winreg)
        _broadcast_env_change(ctypes)

    # ---------- current process PATH (immediate effect) ----------
    proc_parts = [p for p in os.environ.get("PATH", "").split(";") if p]
    proc_out, proc_seen = [], set()
    for p in proc_parts:
        if _dir_contains_exe(p, exe_name, os) and (include_windows_dirs or not _is_windows_rooted(p, os)):
            continue  # drop old providers
        comp = _comp_norm(p, os)
        if comp not in proc_seen:
            proc_out.append(p)
            proc_seen.add(comp)

    if _comp_norm(new_dir, os) not in proc_seen:
        if position == "front":
            proc_out = [new_dir] + proc_out
        else:
            proc_out.append(new_dir)
    os.environ["PATH"] = ";".join(proc_out).strip(";")

    action = "replaced" if replaced_dirs else ("added" if changed else "unchanged")
    return {
        "action": action,
        "new_dir": new_dir,
        "exe_name": exe_name,
        "replaced_dirs": replaced_dirs,
        "scope": scope,
    }


def set_environment_variable(
    name: str,
    value: str,
    scope: Literal["user", "machine"] = "user",                # 'user' or 'machine' (admin required for 'machine')
    expand_for_process: bool = True,    # expand %VARS% for *current* process env only
    broadcast: bool = True              # send WM_SETTINGCHANGE after writing registry
) -> dict:
    """
    Set an environment variable persistently (User or Machine) and update the current process.

    :param name: Name of the environment variable (e.g. 'Path' or 'MyVar').
    :param value: Value to set (e.g. 'C:\MyDir' or
                    'C:\PathWithVars;%OTHER_VAR%\Subdir').
    :param scope: 'user' (no admin) or 'machine' (admin required).
    :param expand_for_process: If True, expand %VARS% in the value for the current process only.
                               The raw value with %VARS% is still stored in the registry.
    :param broadcast: If True, send WM_SETTINGCHANGE to notify other apps of the change.
                      Note: This does not guarantee that other processes will pick up the change.

    Returns:
      {
        'name': 'VarName',
        'value_set': 'raw registry value',
        'reg_type': 'REG_EXPAND_SZ'|'REG_SZ',
        'scope': 'user'|'machine',
        'broadcasted': True|False
      }
    """

    # ---------- inner helpers (no outer vars captured) ----------
    def _get_reg_location(_scope: str, _winreg):
        if _scope == "user":
            return (_winreg.HKEY_CURRENT_USER, r"Environment")
        elif _scope == "machine":
            return (_winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment")
        else:
            raise ValueError("scope must be 'user' or 'machine'")

    # ---------- validate inputs ----------
    if not isinstance(name, str) or not name.strip():
        raise ValueError("name must be a non-empty string")
    if not isinstance(value, str):
        raise ValueError("value must be a string")
    var_name = "Path" if name.strip().lower() == "path" else name.strip()

    # Determine registry type: expand if the string contains %VARS%
    reg_type = winreg.REG_EXPAND_SZ if "%" in value else winreg.REG_SZ

    # ---------- write registry ----------
    root, subkey = _get_reg_location(scope, winreg)
    with winreg.OpenKey(root, subkey, 0, winreg.KEY_SET_VALUE) as k:
        winreg.SetValueEx(k, var_name, 0, reg_type, value)

    # ---------- broadcast change (for new processes to pick it up) ----------
    did_broadcast = False
    if broadcast:
        _broadcast_env_change(ctypes)
        did_broadcast = True

    # ---------- update current process environment ----------
    # For the running Python process, optionally expand for convenience.
    os.environ[var_name] = os.path.expandvars(value) if (expand_for_process and reg_type == winreg.REG_EXPAND_SZ) else value

    return {
        "name": var_name,
        "value_set": value,
        "reg_type": "REG_EXPAND_SZ" if reg_type == winreg.REG_EXPAND_SZ else "REG_SZ",
        "scope": scope,
        "broadcasted": did_broadcast,
    }