"""Install managed GTK and Qt palettes derived from the shell colour scheme."""
import configparser
import io
import json
import os
from pathlib import Path
import re
import tempfile
import shutil
import subprocess
import sys


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
    for name in ("error", "onError"):
        if name in colours and (not isinstance(colours[name], str) or not re.fullmatch(r"[0-9a-fA-F]{6}", colours[name])):
            raise ValueError("Invalid GTK palette colour: " + name)
    aliases = {
        "surface": ("theme_bg_color", "window_bg_color", "view_bg_color", "dialog_bg_color", "popover_bg_color", "theme_base_color"),
        "onSurface": ("theme_fg_color", "window_fg_color", "view_fg_color", "dialog_fg_color", "popover_fg_color", "headerbar_fg_color", "card_fg_color", "sidebar_fg_color", "theme_text_color"),
        "surfaceContainer": ("headerbar_bg_color", "headerbar_backdrop_color", "card_bg_color", "sidebar_bg_color", "sidebar_backdrop_color"),
        "primary": ("accent_color", "accent_bg_color", "theme_selected_bg_color"),
        "onPrimary": ("accent_fg_color", "theme_selected_fg_color"),
        "outlineVariant": ("borders", "sidebar_border_color"),
    }
    definitions = [f"@define-color {alias} {values[role]};" for role, names in aliases.items() for alias in names]
    def blend(left, right, amount):
        return "#" + "".join(f"{round(int(left[i:i+2],16)*(1-amount)+int(right[i:i+2],16)*amount):02x}" for i in (1,3,5))
    surface, ink, container, accent, on_accent, border = (values[k] for k in ("surface","onSurface","surfaceContainer","primary","onPrimary","outlineVariant"))
    hover = blend(container, ink, 0.10)
    pressed = blend(container, ink, 0.18)
    muted = blend(ink, surface, 0.48)
    accent_hover = blend(accent, ink, 0.08)
    error = "#" + colours.get("error", colours["primary"])
    on_error = "#" + colours.get("onError", colours["onPrimary"])
    rules = [
        f"window, window.background, window.dialog, messagedialog, dialog, .dialog, .background {{ background-color: {surface}; color: {ink}; }}",
        f".view, viewport, treeview, iconview, textview, textview text, list, flowbox, gridview, columnview, .content-view, notebook > stack {{ background-color: {surface}; color: {ink}; }}",
        f"headerbar, toolbar, actionbar, statusbar, .toolbar, .sidebar, .navigation-sidebar, notebook > header {{ background-color: {container}; color: {ink}; }}",
        f"popover > contents, menu, menuitem, .menu, tooltip > box, tooltip > decoration, .card, .boxed-list, .boxed-list > row {{ background-color: {container}; color: {ink}; }}",
        f"window.popup, window.popup.background, window.tooltip, tooltip, popover, popover.background {{ background-color: transparent; background-image: none; box-shadow: none; }}",
        f"tooltip > box {{ background-color: {container}; color: {ink}; border-radius: 8px; }}",
        f"label, image {{ color: inherit; }}",
        f"button {{ border-radius: 10px; background-image: none; background-color: {container}; color: {ink}; border: 1px solid {border}; box-shadow: none; text-shadow: none; }}",
        f"button:hover {{ background-image: none; background-color: {hover}; color: {ink}; }}",
        f"button:active, button:checked, button:checked:hover {{ background-image: none; background-color: {accent}; color: {on_accent}; border-color: {accent}; }}",
        f"button:disabled, button:disabled:hover, button:disabled:checked {{ background-image: none; background-color: {container}; color: {muted}; border-color: {border}; }}",
        f"button.flat, button.flat.image-button, button.titlebutton {{ background-color: transparent; border-color: transparent; }}",
        f"button.flat:hover, button.flat.image-button:hover, button.titlebutton:hover {{ background-color: {hover}; color: {ink}; }}",
        f"button.flat:active, button.flat:checked {{ background-color: {pressed}; color: {ink}; }}",
        f"button.suggested-action, button.suggested-action:checked {{ background-image: none; background-color: {accent}; color: {on_accent}; border-color: {accent}; }}",
        f"button.suggested-action:hover, button.suggested-action:active {{ background-color: {accent_hover}; color: {on_accent}; }}",
        f"button.destructive-action {{ background-image: none; background-color: {error}; color: {on_error}; border-color: {error}; }}",
        f"button.destructive-action:hover, button.destructive-action:active {{ background-color: {blend(error, ink, .10)}; color: {on_error}; }}",
        f"entry, textview, spinbutton, searchentry, dropdown, combobox {{ background-color: {container}; background-image: none; color: {ink}; border-color: {border}; }}",
        f"entry {{ border-radius: 8px; border: 1px solid {border}; }}",
        f"entry:focus, entry:focus-within, spinbutton:focus-within {{ border-color: {accent}; }}",
        f"selection, text selection, entry selection, row:selected, treeview:selected, .view:selected, menuitem:hover {{ background-color: {accent}; color: {on_accent}; }}",
        f"row:hover, flowboxchild:hover {{ background-color: {hover}; }}",
        f"switch, scale trough, progressbar trough {{ background-color: {container}; border-color: {border}; }}",
        f"switch:checked, scale highlight, progressbar progress, check:checked, radio:checked {{ background-color: {accent}; color: {on_accent}; border-color: {accent}; }}",
        f"switch slider, scale slider {{ background-color: {ink}; border-color: {border}; }}",
        f"check, radio {{ background-color: {container}; border-color: {border}; color: {ink}; }}",
        f"separator {{ background-color: {border}; min-width: 1px; min-height: 1px; }}",
        f"*:disabled {{ color: {muted}; }}",
    ]
    css = "/* Generated from the hics palette. */\n" + "\n".join(definitions + rules) + "\n"
    # GTK2 has no CSS support; it needs a real RC palette, not GTK3 theme names.
    rc = ["# Generated from the hics palette.", 'style "hics-palette" {', '  xthickness = 2', '  ythickness = 2']
    for state, bg, fg in (("NORMAL",surface,ink),("PRELIGHT",hover,ink),("ACTIVE",pressed,ink),("SELECTED",accent,on_accent),("INSENSITIVE",container,muted)):
        rc += [f'  bg[{state}] = "{bg}"', f'  base[{state}] = "{surface if state == "NORMAL" else bg}"', f'  fg[{state}] = "{fg}"', f'  text[{state}] = "{fg}"']
    rc += ['}', 'class "*" style "hics-palette"', 'widget_class "*" style "hics-palette"', '']
    gtk2 = Path(config_root) / "gtk-2.0"
    atomic_text(gtk2 / "hics.gtkrc", "\n".join(rc))
    gtkrc = gtk2 / "gtkrc"
    previous = gtkrc.read_text() if gtkrc.is_file() else ""
    previous = re.sub(r'(?m)^\s*include\s+"[^"\n]*/?hics\.gtkrc"\s*$', '', previous)
    atomic_text(gtkrc, previous.rstrip() + "\ninclude " + json.dumps(str(gtk2 / "hics.gtkrc")) + "\n")
    for version in ("3.0", "4.0"):
        directory = Path(config_root) / ("gtk-" + version)
        toolkit_css = css.replace(":focus-within", ":focus") if version == "3.0" else css
        if version == "4.0":
            # libadwaita 1.6+ uses inherited CSS variables rather than the old
            # named colours for many controls and accent-button variants.
            variables = {
                "window-bg-color":surface,"window-fg-color":ink,"view-bg-color":surface,"view-fg-color":ink,
                "headerbar-bg-color":container,"headerbar-fg-color":ink,"headerbar-backdrop-color":container,
                "card-bg-color":container,"card-fg-color":ink,"popover-bg-color":container,"popover-fg-color":ink,
                "dialog-bg-color":surface,"dialog-fg-color":ink,"sidebar-bg-color":container,"sidebar-fg-color":ink,
                "sidebar-backdrop-color":container,"sidebar-border-color":border,"accent-bg-color":accent,
                "accent-fg-color":on_accent,"accent-color":accent,"destructive-bg-color":error,
                "destructive-fg-color":on_error,"destructive-color":error,"border-color":border,
            }
            toolkit_css += "window { " + " ".join(f"--{key}: {value};" for key,value in variables.items()) + " }\n"
        atomic_text(directory / "hics.css", toolkit_css)
        main = directory / "gtk.css"
        # Hyprstack owns toolkit styling. Drop legacy imports (Noctalia,
        # libadwaita overrides, etc.) instead of mixing unrelated palettes.
        atomic_text(main, '@import url("hics.css");\n')
        # Replace old dark-theme symlinks as well; never write through them.
        atomic_text(directory / "gtk-dark.css", '@import url("hics.css");\n')
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
        colour_file = folder / "colors/hics.conf"
        atomic_text(colour_file, "[ColorScheme]\n" +
                    f"active_colors={palette}\ninactive_colors={palette}\ndisabled_colors={disabled_palette}\n")
        update_settings(folder / f"qt{version}ct.conf", "Appearance", {
            "color_scheme_path": str(colour_file), "custom_palette": "true", "style": "Fusion",
        })

    # KDE runtimes usually use the KDE platform theme rather than qt*ct.
    # Supply its native palette too; do not require host Qt plugins in a sandbox.
    rgb = lambda role: ",".join(str(int(colours[role][i:i+2], 16)) for i in (0, 2, 4))
    for group, background, foreground in (
        ("Window", "surface", "onSurface"), ("View", "surface", "onSurface"),
        ("Button", "surfaceContainer", "onSurface"), ("Selection", "primary", "onPrimary"),
        ("Tooltip", "surfaceContainer", "onSurface"), ("Complementary", "surfaceContainer", "onSurface"),
        ("Header", "surfaceContainer", "onSurface"),
    ):
        update_settings(Path(config_root) / "kdeglobals", "Colors:" + group, {
            "BackgroundNormal": rgb(background), "BackgroundAlternate": rgb(background),
            "ForegroundNormal": rgb(foreground), "ForegroundInactive": rgb("outlineVariant"),
            "ForegroundLink": rgb("primary"), "DecorationFocus": rgb("primary"),
            "DecorationHover": rgb("primary"),
        })
    update_settings(Path(config_root) / "kdeglobals", "General", {"ColorScheme": "Hyprstack"})


_synced_flatpaks = set()


def installed_flatpaks():
    if not shutil.which("flatpak"):
        return []
    result = subprocess.run(["flatpak", "list", "--app", "--columns=application"],
                            capture_output=True, text=True, timeout=15, check=True)
    return sorted({app for app in result.stdout.splitlines()
                   if re.fullmatch(r"[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+){2,}", app)})


def sync_flatpaks(colours, mode=None, only_new=False):
    """Write each app's private XDG config without granting host filesystem access."""
    try:
        installed = set(installed_flatpaks())
    except (OSError, subprocess.SubprocessError) as error:
        print("Unable to list Flatpak applications:", error, file=sys.stderr)
        return
    _synced_flatpaks.intersection_update(installed)
    for app in sorted(installed - _synced_flatpaks if only_new else installed):
        base = Path.home() / ".var/app" / app / "config"
        # Do not let configuration symlinks overwrite another application's
        # settings (or a host theme) while synchronising private sandboxes.
        managed = ("gtk-2.0", "gtk-3.0", "gtk-4.0", "qt5ct", "qt6ct")
        if any(parent.is_symlink() for parent in (base, base.parent, base.parent.parent, base.parent.parent.parent)) or any((base / name).is_symlink() for name in (*managed, "qt5ct/colors", "qt6ct/colors")):
            print("Skipping symlinked Flatpak config:", app, file=sys.stderr)
            continue
        try:
            apply_palette(colours, base, mode)
        except (OSError, ValueError, configparser.Error) as error:
            print("Unable to theme Flatpak application", app + ":", error, file=sys.stderr)
        else:
            _synced_flatpaks.add(app)


def apply_desktop_palette(colours, config_root, mode=None):
    apply_palette(colours, config_root, mode)
    sync_flatpaks(colours, mode)


def install_legacy_gtk2(config_root):
    # Apps started outside the session wrapper still read ~/.gtkrc-2.0.
    legacy = Path.home() / ".gtkrc-2.0"
    previous = legacy.read_text() if legacy.is_file() else ""
    marker = "# hics managed palette"
    previous = re.sub(r'(?m)^# hics managed palette\ninclude "[^"\n]+"\n?', '', previous)
    atomic_text(legacy, previous.rstrip() + "\n" + marker + "\ninclude " + json.dumps(str(Path(config_root) / "gtk-2.0/gtkrc")) + "\n")


def sync_new_flatpaks():
    state = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state")) / "hics/scheme.json"
    if state.exists():
        scheme = json.loads(state.read_text())
        sync_flatpaks(scheme["colours"], scheme.get("mode"), only_new=True)



def restore():
    state = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state")) / "hics/scheme.json"
    if state.exists():
        scheme = json.loads(state.read_text())
        apply_desktop_palette(scheme["colours"], Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")), scheme.get("mode"))
        install_legacy_gtk2(Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")))
    else:
        # Packages cannot configure an arbitrary user's home during root install.
        # The shared session entry point installs defaults at the first login.
        import theme_manager
        theme_manager.apply_theme("catppuccin", "dark")
        install_legacy_gtk2(Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")))


if __name__ == "__main__":
    restore()
