import configparser
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "shell/assets"))
import gtk_theme


class FlatpakPaletteTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.home = Path(self.temporary.name)
        self.colours = dict.fromkeys(("surface", "onSurface", "surfaceContainer", "primary", "onPrimary", "outlineVariant"), "112233")
        gtk_theme._synced_flatpaks.clear()
        self.addCleanup(gtk_theme._synced_flatpaks.clear)

    def test_discovery_deduplicates_and_rejects_non_app_identifiers(self):
        result = subprocess.CompletedProcess([], 0, "org.example.App\norg.example.App\n../../escape\n--system\n", "")
        with patch("gtk_theme.shutil.which", return_value="/usr/bin/flatpak"), patch("gtk_theme.subprocess.run", return_value=result) as run:
            self.assertEqual(gtk_theme.installed_flatpaks(), ["org.example.App"])
        self.assertEqual(run.call_args.args[0], ["flatpak", "list", "--app", "--columns=application"])

    def test_installs_private_gtk_and_kde_palettes_without_permission_overrides(self):
        apps = ["org.example.Gtk", "org.example.Kde"]
        with patch("gtk_theme.Path.home", return_value=self.home), patch("gtk_theme.installed_flatpaks", return_value=apps), patch("gtk_theme.subprocess.run") as run:
            gtk_theme.sync_flatpaks(self.colours, "dark")
            self.colours["primary"] = "aabbcc"
            gtk_theme.sync_flatpaks(self.colours, "light")
        run.assert_not_called()
        for app in apps:
            base = self.home / ".var/app" / app / "config"
            self.assertIn("#aabbcc", (base / "gtk-4.0/hyprstack.css").read_text())
            settings = configparser.ConfigParser()
            settings.read(base / "kdeglobals")
            self.assertEqual(settings.get("Colors:Selection", "BackgroundNormal"), "170,187,204")
            settings.read(base / "qt6ct/qt6ct.conf")
            self.assertEqual(settings.get("Appearance", "color_scheme_path"), str(base / "qt6ct/colors/hyprstack.conf"))
            self.assertTrue((base / "gtk-3.0/gtk.css").is_file())

    def test_periodic_sync_only_configures_new_apps(self):
        with patch("gtk_theme.Path.home", return_value=self.home), patch("gtk_theme.installed_flatpaks", side_effect=[["org.example.One"], ["org.example.One", "org.example.Two"]]), patch("gtk_theme.apply_palette") as apply:
            gtk_theme.sync_flatpaks(self.colours, only_new=True)
            gtk_theme.sync_flatpaks(self.colours, only_new=True)
        self.assertEqual(apply.call_count, 2)
        self.assertIn("org.example.Two", str(apply.call_args.args[1]))

    def test_symlinked_config_cannot_modify_host(self):
        base = self.home / ".var/app/org.example.App/config"
        base.mkdir(parents=True)
        target = self.home / "unrelated"
        target.mkdir()
        (base / "gtk-4.0").symlink_to(target, target_is_directory=True)
        with patch("gtk_theme.Path.home", return_value=self.home), patch("gtk_theme.installed_flatpaks", return_value=["org.example.App"]):
            gtk_theme.sync_flatpaks(self.colours)
        self.assertEqual(list(target.iterdir()), [])

    def test_without_flatpak_there_is_nothing_to_install(self):
        with patch("gtk_theme.shutil.which", return_value=None), patch("gtk_theme.subprocess.run") as run:
            self.assertEqual(gtk_theme.installed_flatpaks(), [])
        run.assert_not_called()

    def test_flatpak_failure_does_not_prevent_host_theme_changes(self):
        with patch("gtk_theme.installed_flatpaks", side_effect=subprocess.TimeoutExpired("flatpak", 15)):
            gtk_theme.apply_desktop_palette(self.colours, self.home / "config")
        self.assertTrue((self.home / "config/gtk-3.0/hyprstack.css").is_file())
