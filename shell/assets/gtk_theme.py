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
    aliases = {
        "surface": ("theme_bg_color", "window_bg_color", "view_bg_color", "dialog_bg_color", "popover_bg_color", "theme_base_color"),
        "onSurface": ("theme_fg_color", "window_fg_color", "view_fg_color", "dialog_fg_color", "popover_fg_color", "headerbar_fg_color", "card_fg_color", "sidebar_fg_color", "theme_text_color"),
        "surfaceContainer": ("headerbar_bg_color", "headerbar_backdrop_color", "card_bg_color", "sidebar_bg_color", "sidebar_backdrop_color"),
        "primary": ("accent_color", "accent_bg_color", "theme_selected_bg_color"),
        "onPrimary": ("accent_fg_color", "theme_selected_fg_color"),
        "outlineVariant": ("borders", "sidebar_border_color"),
    }
    definitions = [f"@define-color {alias} {values[role]};" for role, names in aliases.items() for alias in names]
    css = "/* Generated from the Hyprstack palette. */\n" + "\n".join(definitions + [
        f"@define-color window_bg_color {values['surface']};",
        f"@define-color window_fg_color {values['onSurface']};",
        f"@define-color accent_bg_color {values['primary']};",
        f"@define-color accent_fg_color {values['onPrimary']};",
        f"window, window.background, window.dialog, messagedialog, dialog, .dialog, .background {{ background-color: {values['surface']}; color: {values['onSurface']}; }}",
        f"headerbar, toolbar {{ background-color: {values['surfaceContainer']}; color: {values['onSurface']}; border: none; }}",
        f"button {{ border-radius: 12px; background-image: none; background-color: {values['surfaceContainer']}; color: {values['onSurface']}; border: 1px solid {values['outlineVariant']}; }}",
        f"button.suggested-action {{ background-color: {values['primary']}; color: {values['onPrimary']}; }}",
        f"entry, textview, textview text, spinbutton {{ border-radius: 10px; background-color: {values['surfaceContainer']}; color: {values['onSurface']}; border: 1px solid {values['outlineVariant']}; }}",
        f"entry:focus {{ border-color: {values['primary']}; }}",
    ]) + "\n"
    for version in ("3.0", "4.0"):
        directory = Path(config_root) / ("gtk-" + version)
        atomic_text(directory / "hyprstack.css", css)
        main = directory / "gtk.css"
        existing = main.read_text() if main.exists() else ""
        include = '@import url("hyprstack.css");'
        # User CSS has the same priority: later imports win. Migrate the old
        # leading import as well as single-quoted variants without deleting styles.
        existing = re.sub(r"@import\s+url\(\s*['\"]hyprstack\.css['\"]\s*\)\s*;[ \t]*\n?", "", existing)
        updated = existing.rstrip() + ("\n" if existing.strip() else "") + include + "\n"
        if not main.exists() or main.read_text() != updated:
            atomic_text(main, updated)


def restore():
    state = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state")) / "hyprstack/scheme.json"
    if state.exists():
        scheme = json.loads(state.read_text())
        apply_palette(scheme["colours"], Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")))
