"""Dispatchers Lua historiques : formes conservées, entrées strictement bornées."""
import subprocess


def focus_workspace(number: int, style: str = "mode") -> None:
    if type(number) is not int or not 1 <= number <= 9:
        raise ValueError("Workspace hors limites")
    if style == "session":
        args = ["hyprctl", "eval", f"hl.dispatch(hl.dsp.focus({{workspace={number}}}))"]
    elif style == "mode":
        args = ["hyprctl", "dispatch", f'hl.dsp.focus({{ workspace = "{number}" }})']
    elif style == "command":
        args = ["hyprctl", "dispatch", f"hl.dsp.focus({{workspace={number}}})"]
    else:
        raise ValueError("Style de dispatcher inconnu")
    result = subprocess.run(args, capture_output=True, text=True, timeout=5, check=False)
    if result.returncode != 0 or "error:" in result.stdout.lower():
        raise RuntimeError("Changement de workspace refusé par Hyprland")
