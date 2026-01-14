import re
import os
import time
from typing import Optional, Union

if os.name == "nt":
    from pywinauto import Desktop
    from pywinauto.base_wrapper import BaseWrapper

TitleType = Union[str, re.Pattern]


def _normalize(s: str) -> str:
    s = s.replace("&", "")
    s = re.sub(r"\s+", " ", s).strip()
    return s.casefold()


def _window_title_matches(title: str, window_title: Optional[TitleType], partial: bool) -> bool:
    if window_title is None:
        return True
    if isinstance(window_title, re.Pattern):
        return bool(window_title.search(title))
    if partial:
        return _normalize(window_title) in _normalize(title)
    return title == window_title


def _as_wrapper(obj):
    # WindowSpecification has wrapper_object(); wrappers (ButtonWrapper, etc.) do not.
    return obj.wrapper_object() if hasattr(obj, "wrapper_object") else obj


def find_button(
    button_text: str,
    window_title: Optional[TitleType] = None,
    window_title_partial: bool = False,
    pid: Optional[int] = None,
) -> Optional[BaseWrapper]:
    target = _normalize(button_text)

    # ---------- UIA backend ----------
    try:
        desktop = Desktop(backend="uia")
        for w in desktop.windows():
            try:
                if pid is not None and getattr(w.element_info, "process_id", None) != pid:
                    continue

                wt = w.window_text()
                if not _window_title_matches(wt, window_title, partial=window_title_partial):
                    continue

                # Exact match Buttons
                for ctrl in w.descendants(control_type="Button"):
                    try:
                        name = ctrl.window_text() or ctrl.element_info.name or ""
                        if _normalize(name) == target and ctrl.is_visible() and ctrl.is_enabled():
                            return _as_wrapper(ctrl)  # ctrl is usually already a wrapper
                    except Exception:
                        continue

                # Exact match CheckBoxes (some installers use checkbox for acceptance)
                for ctrl in w.descendants(control_type="CheckBox"):
                    try:
                        name = ctrl.window_text() or ctrl.element_info.name or ""
                        if _normalize(name) == target and ctrl.is_visible() and ctrl.is_enabled():
                            return _as_wrapper(ctrl)
                    except Exception:
                        continue

                # Partial match Buttons
                for ctrl in w.descendants(control_type="Button"):
                    try:
                        name = ctrl.window_text() or ctrl.element_info.name or ""
                        if target in _normalize(name) and ctrl.is_visible() and ctrl.is_enabled():
                            return _as_wrapper(ctrl)
                    except Exception:
                        continue

            except Exception:
                continue
    except Exception:
        pass

    # ---------- Win32 backend fallback ----------
    try:
        desktop = Desktop(backend="win32")
        for w in desktop.windows():
            try:
                if pid is not None and getattr(w.element_info, "process_id", None) != pid:
                    continue

                wt = w.window_text()
                if not _window_title_matches(wt, window_title, partial=window_title_partial):
                    continue

                for ctrl in w.children(class_name="Button"):
                    try:
                        name = ctrl.window_text() or ""
                        n = _normalize(name)
                        if (n == target or target in n) and ctrl.is_visible() and ctrl.is_enabled():
                            return _as_wrapper(ctrl)
                    except Exception:
                        continue

            except Exception:
                continue
    except Exception:
        pass

    return None


def click_button(
    button_text: str,
    window_title: Optional[TitleType] = None,
    timeout: float = 5.0,
    window_title_partial: bool = False,
    pid: Optional[int] = None,
    poll_interval: float = 0.2,
    relax_pid_after: Optional[float] = 5.0,
    focus_before_click: bool = True,
) -> bool:
    r"""
    Wait for a control (Button/CheckBox) with the given text to become visible+enabled and click it.

    Returns:
        True  - if the control was found and clicked within timeout
        False - if not found within timeout

    Notes:
        - If pid is provided, we try pid-scoped search first.
        - If relax_pid_after is not None, after that many seconds we retry with pid=None
          (useful when installers spawn a separate UI process).


    Example Implementation:
        def run_installer_wait(file_path: str, args: Optional[List[str]] = None) -> int:
        \"\"\"
        Run an installer EXE directly and wait for completion.
        Returns the installer's exit code.

        Important:
        - For GUI installers, this blocks until the installer process exits.
        - Some installers spawn child processes and exit early; if that happens,
          we can add a more advanced wait strategy. (Npcap typically does not.)
        \"\"\"
        cmd = [file_path] + (args or [])
        proc = subprocess.Popen(cmd)

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
    """
    start = time.time()
    deadline = start + timeout

    while time.time() < deadline:
        effective_pid = pid
        if pid is not None and relax_pid_after is not None:
            if (time.time() - start) >= relax_pid_after:
                effective_pid = None

        ctrl = find_button(
            button_text=button_text,
            window_title=window_title,
            window_title_partial=window_title_partial,
            pid=effective_pid,
        )

        if ctrl is not None:
            if focus_before_click:
                try:
                    ctrl.set_focus()
                except Exception:
                    pass

            # click_input works for both ButtonWrapper and CheckBoxWrapper in practice
            try:
                ctrl.click_input()
            except Exception:
                # fallback for some controls
                try:
                    ctrl.click()
                except Exception:
                    return False

            return True

        time.sleep(poll_interval)

    return False


def dump_uia_controls():
    d = Desktop(backend="uia")
    for w in d.windows():
        try:
            print("WINDOW:", repr(w.window_text()), "PID:", w.element_info.process_id)
            for ctrl in w.descendants(control_type="Button"):
                name = ctrl.window_text() or ctrl.element_info.name or ""
                if name:
                    print("  [Button]", repr(name))
            for ctrl in w.descendants(control_type="CheckBox"):
                name = ctrl.window_text() or ctrl.element_info.name or ""
                if name:
                    print("  [CheckBox]", repr(name))
        except Exception:
            continue
