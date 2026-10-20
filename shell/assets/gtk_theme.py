"""Apply the shell palette to GTK dialogs without replacing user stylesheets."""
import json
import os
from pathlib import Path
import re
import tempfile


def atomic_text(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix=".hyprstack-")
    try:
        with os.fdopen(fd, "w") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def apply_palette(colours, config_root):
    names = ("surface", "onSurface", "surfaceContainer", "primary", "onPrimary", "outlineVariant")
    values = {}
    for name in names:
        value = colours.get(name, "")
        if not isinstance(value, str) or not re.fullmatch(r"[0-9a-fA-F]{6}", value):
            raise ValueError("Invalid GTK palette colour: " + name)
        values[name] = "#" + value
    css = "/* Generated from the Hyprstack palette. */\n" + "\n".join([
        f"@define-color window_bg_color {values['surface']};",
        f"@define-color window_fg_color {values['onSurface']};",
        f"@define-color accent_bg_color {values['primary']};",
        f"@define-color accent_fg_color {values['onPrimary']};",
        f"window.background, window.dialog, messagedialog {{ background-color: {values['surface']}; color: {values['onSurface']}; }}",
        f"headerbar, toolbar {{ background-color: {values['surfaceContainer']}; color: {values['onSurface']}; border: none; }}",
        f"button {{ border-radius: 12px; background-image: none; background-color: {values['surfaceContainer']}; color: {values['onSurface']}; border: 1px solid {values['outlineVariant']}; }}",
        f"button.suggested-action {{ background-color: {values['primary']}; color: {values['onPrimary']}; }}",
        f"entry {{ border-radius: 10px; background-color: {values['surfaceContainer']}; color: {values['onSurface']}; border: 1px solid {values['outlineVariant']}; }}",
        f"entry:focus {{ border-color: {values['primary']}; }}",
    ]) + "\n"
    for version in ("3.0", "4.0"):
        directory = Path(config_root) / ("gtk-" + version)
        atomic_text(directory / "hyprstack.css", css)
        main = directory / "gtk.css"
        existing = main.read_text() if main.exists() else ""
        include = '@import url("hyprstack.css");'
        if include not in existing:
            atomic_text(main, include + "\n" + existing)


def restore():
    state = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state")) / "hyprstack/scheme.json"
    if state.exists():
        scheme = json.loads(state.read_text())
        apply_palette(scheme["colours"], Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")))
