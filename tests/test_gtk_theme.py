import sys
import os
import tempfile
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "shell/assets"))
from gtk_theme import apply_palette


class GtkPaletteTests(unittest.TestCase):
    def test_fresh_install_initialises_a_shared_default_palette(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            environment = dict(os.environ, HOME=str(root), XDG_CONFIG_HOME=str(root / "config"), XDG_DATA_HOME=str(root / "data"), XDG_STATE_HOME=str(root / "state"))
            binary = root / "bin/flatpak"
            binary.parent.mkdir()
            binary.write_text("#!/bin/sh\nprintf '%s\\n' org.example.Installed\n")
            binary.chmod(0o755)
            environment["PATH"] = str(binary.parent) + os.pathsep + os.environ.get("PATH", "")
            helper = Path(__file__).resolve().parents[1] / "shell/assets/gtk_theme.py"
            subprocess.run([sys.executable, str(helper)], env=environment, check=True, capture_output=True)
            self.assertTrue((root / "state/hics/scheme.json").is_file())
            self.assertTrue((root / "config/gtk-4.0/hics.css").is_file())
            self.assertTrue((root / "config/qt6ct/colors/hics.conf").is_file())
            self.assertTrue((root / ".var/app/org.example.Installed/config/gtk-4.0/hics.css").is_file())

    def test_replaces_dark_theme_symlink_without_modifying_its_target(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            original = root / "old.css"
            original.write_text("old theme")
            folder = root / "gtk-4.0"
            folder.mkdir()
            (folder / "gtk-dark.css").symlink_to(original)
            colours = dict.fromkeys(("surface", "onSurface", "surfaceContainer", "primary", "onPrimary", "outlineVariant"), "112233")
            apply_palette(colours, root)
            self.assertFalse((folder / "gtk-dark.css").is_symlink())
            self.assertEqual(original.read_text(), "old theme")

    def test_replaces_legacy_theme_overrides(self):
        colours = dict.fromkeys(("surface", "onSurface", "surfaceContainer", "primary", "onPrimary", "outlineVariant"), "112233")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            folder = root / "gtk-3.0"
            folder.mkdir()
            main = folder / "gtk.css"
            main.write_text("@import url('hics.css');\n@import url(\"noctalia.css\");\nbutton { color: red; }\n")
            apply_palette(colours, root)
            result = main.read_text()
            self.assertTrue(result.endswith('@import url("hics.css");\n'))
            self.assertNotIn('button { color: red; }', result)
            self.assertNotIn('noctalia', result)
            self.assertEqual(result.count('hics.css'), 1)
            css = (folder / "hics.css").read_text()
            for name in ("theme_bg_color", "theme_text_color", "dialog_bg_color", "view_bg_color", "headerbar_bg_color"):
                self.assertIn(f"@define-color {name} #112233;", css)

    def test_saving_a_shell_theme_also_updates_dialog_colours(self):
        import theme_manager
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            colours = theme_manager.palette({"background":"101018", "foreground":"e0e0e0", "accent":"aaccee"}, "dark")
            with patch.object(theme_manager, "STATE", root / "state"), patch("gtk_theme.sync_flatpaks"), patch.dict(os.environ, {"XDG_CONFIG_HOME":str(root / "config")}):
                theme_manager.save_current({"mode":"dark", "colours":colours})
            self.assertTrue((root / "state/scheme.json").exists())
            self.assertIn("#" + colours["primary"], (root / "config/gtk-3.0/hics.css").read_text())
            self.assertTrue((root / "config/gtk-4.0/hics.css").exists())

    def test_replaces_custom_css_and_updates_managed_palette(self):
        colours = dict.fromkeys(("surface", "onSurface", "surfaceContainer", "primary", "onPrimary", "outlineVariant"), "112233")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "gtk-3.0").mkdir()
            custom = root / "gtk-3.0/gtk.css"
            custom.write_text("/* personal rules */\n")
            apply_palette(colours, root)
            colours["primary"] = "aabbcc"
            apply_palette(colours, root)
            self.assertNotIn("personal rules", custom.read_text())
            self.assertEqual(custom.read_text().count('@import url("hics.css");'), 1)
            for version in ("3.0", "4.0"):
                self.assertIn("#aabbcc", (root / f"gtk-{version}/hics.css").read_text())

    def test_dark_and_light_schemes_update_both_toolkits(self):
        import configparser
        import theme_manager
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for mode, background in (("dark", "101018"), ("light", "fafafa")):
                colours = theme_manager.palette({"background":background, "foreground":"808080", "accent":"aaccee"}, mode)
                apply_palette(colours, root, mode)
                for version in ("3.0", "4.0"):
                    settings = configparser.ConfigParser()
                    settings.read(root / f"gtk-{version}/settings.ini")
                    self.assertEqual(settings.getboolean("Settings", "gtk-application-prefer-dark-theme"), mode == "dark")
                for version in (5, 6):
                    folder = root / f"qt{version}ct"
                    settings = configparser.ConfigParser()
                    settings.read(folder / f"qt{version}ct.conf")
                    self.assertTrue(settings.getboolean("Appearance", "custom_palette"))
                    self.assertEqual(settings.get("Appearance", "color_scheme_path"), str(folder / "colors/hics.conf"))
                    settings.read(folder / "colors/hics.conf")
                    active = settings.get("ColorScheme", "active_colors").split(", ")
                    self.assertEqual(len(active), 22)
                    self.assertEqual(active[10], "#ff" + colours["surface"])
                    self.assertEqual(active[12], "#ff" + colours["primary"])

    def test_rejects_css_injection_before_writing(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                apply_palette({"surface": "red; }"}, Path(directory))
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_gtk2_preserves_preferences_and_replaces_managed_include(self):
        colours = dict.fromkeys(("surface", "onSurface", "surfaceContainer", "primary", "onPrimary", "outlineVariant"), "112233")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "gtk-2.0").mkdir()
            rc = root / "gtk-2.0/gtkrc"
            rc.write_text('gtk-icon-theme-name="my-icons"\ngtk-cursor-theme-name="my-cursor"\n')
            apply_palette(colours, root)
            apply_palette(colours, root)
            self.assertIn('gtk-icon-theme-name="my-icons"', rc.read_text())
            self.assertIn('gtk-cursor-theme-name="my-cursor"', rc.read_text())
            self.assertEqual(rc.read_text().count('hics.gtkrc'), 1)
            palette = (root / "gtk-2.0/hics.gtkrc").read_text()
            self.assertIn('#112233', palette)
            self.assertIn('SELECTED', palette)

    def test_gtk4_variables_and_button_states_are_generated_for_light_and_dark(self):
        for mode, surface, ink in (("dark", "101018", "e0e0e0"), ("light", "f0f0f8", "202028")):
            colours = dict(surface=surface, onSurface=ink, surfaceContainer=surface, primary="aaccee", onPrimary="102030", outlineVariant="505060")
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                apply_palette(colours, root, mode)
                css = (root / "gtk-4.0/hics.css").read_text()
                self.assertIn('--window-bg-color: #' + surface, css)
                self.assertIn('--window-fg-color: #' + ink, css)
                for selector in ('button:checked', 'button:disabled', 'button.suggested-action', 'button.destructive-action', 'button.flat'):
                    self.assertIn(selector, css)
                self.assertNotIn(':focus-within', (root / 'gtk-3.0/hics.css').read_text())

    def test_rejects_invalid_optional_colours(self):
        colours = dict.fromkeys(("surface", "onSurface", "surfaceContainer", "primary", "onPrimary", "outlineVariant"), "112233")
        for value in (None, 'red; }', 42):
            with tempfile.TemporaryDirectory() as directory, self.assertRaises(ValueError):
                apply_palette(dict(colours, error=value), Path(directory))
