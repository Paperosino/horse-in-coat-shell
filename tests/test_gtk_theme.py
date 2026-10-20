import sys
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "shell/assets"))
from gtk_theme import apply_palette


class GtkPaletteTests(unittest.TestCase):
    def test_saving_a_shell_theme_also_updates_dialog_colours(self):
        import theme_manager
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            colours = theme_manager.palette({"background":"101018", "foreground":"e0e0e0", "accent":"aaccee"}, "dark")
            with patch.object(theme_manager, "STATE", root / "state"), patch.dict(os.environ, {"XDG_CONFIG_HOME":str(root / "config")}):
                theme_manager.save_current({"mode":"dark", "colours":colours})
            self.assertTrue((root / "state/scheme.json").exists())
            self.assertIn("#" + colours["primary"], (root / "config/gtk-3.0/hyprstack.css").read_text())
            self.assertTrue((root / "config/gtk-4.0/hyprstack.css").exists())

    def test_preserves_custom_css_and_updates_managed_palette(self):
        colours = dict.fromkeys(("surface", "onSurface", "surfaceContainer", "primary", "onPrimary", "outlineVariant"), "112233")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "gtk-3.0").mkdir()
            custom = root / "gtk-3.0/gtk.css"
            custom.write_text("/* personal rules */\n")
            apply_palette(colours, root)
            colours["primary"] = "aabbcc"
            apply_palette(colours, root)
            self.assertIn("personal rules", custom.read_text())
            self.assertEqual(custom.read_text().count('@import url("hyprstack.css");'), 1)
            for version in ("3.0", "4.0"):
                self.assertIn("#aabbcc", (root / f"gtk-{version}/hyprstack.css").read_text())

    def test_rejects_css_injection_before_writing(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                apply_palette({"surface": "red; }"}, Path(directory))
            self.assertEqual(list(Path(directory).iterdir()), [])
