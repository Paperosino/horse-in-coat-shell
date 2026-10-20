"""Install managed GTK and Qt palettes derived from the shell colour scheme."""
import configparser
import io
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


def update_settings(path, section, values):
    settings = configparser.ConfigParser(interpolation=None, strict=False)
    settings.optionxform = str
    if path.exists():
        settings.read(path)
    if not settings.has_section(section):
        settings.add_section(section)
    for key, value in values.items():
        settings.set(section, key, str(value))
    stream = io.StringIO()
    settings.write(stream, space_around_delimiters=False)
    atomic_text(path, stream.getvalue())


def apply_palette(colours, config_root, mode=None):
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
        # Hyprstack owns toolkit styling. Drop legacy imports (Noctalia,
        # libadwaita overrides, etc.) instead of mixing unrelated palettes.
        atomic_text(main, '@import url("hyprstack.css");\n')
        # Replace old dark-theme symlinks as well; never write through them.
        atomic_text(directory / "gtk-dark.css", '@import url("hyprstack.css");\n')
        dark = mode == "dark" if mode else sum(int(colours["surface"][i:i+2], 16) * weight for i, weight in ((0,.2126),(2,.7152),(4,.0722))) < 128
        update_settings(directory / "settings.ini", "Settings", {
            "gtk-theme-name": "Adwaita",
            "gtk-application-prefer-dark-theme": int(dark),
        })
    # QPalette colour-role order, used by both qt5ct and qt6ct. Preserve
    # icon/font preferences while replacing the palette and widget style.
    roles = ("onSurface", "surfaceContainer", "surfaceContainer", "surfaceContainer",
             "outlineVariant", "outlineVariant", "onSurface", "onSurface",
             "onSurface", "surface", "surface", "outlineVariant", "primary",
             "onPrimary", "primary", "primary", "surfaceContainer", "onSurface",
             "surfaceContainer", "onSurface", "outlineVariant", "primary")
    palette = ", ".join("#ff" + colours[role] for role in roles)
    disabled = list(roles)
    for index in (0, 6, 8, 19):
        disabled[index] = "outlineVariant"
    disabled_palette = ", ".join("#ff" + colours[role] for role in disabled)
    for version in (5, 6):
        folder = Path(config_root) / f"qt{version}ct"
        colour_file = folder / "colors/hyprstack.conf"
        atomic_text(colour_file, "[ColorScheme]\n" +
                    f"active_colors={palette}\ninactive_colors={palette}\ndisabled_colors={disabled_palette}\n")
        update_settings(folder / f"qt{version}ct.conf", "Appearance", {
            "color_scheme_path": str(colour_file), "custom_palette": "true", "style": "Fusion",
        })



def restore():
    state = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state")) / "hyprstack/scheme.json"
    if state.exists():
        scheme = json.loads(state.read_text())
        apply_palette(scheme["colours"], Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")), scheme.get("mode"))
    else:
        # Packages cannot configure an arbitrary user's home during root install.
        # The shared session entry point installs defaults at the first login.
        import theme_manager
        theme_manager.apply_theme("catppuccin", "dark")


if __name__ == "__main__":
    restore()
