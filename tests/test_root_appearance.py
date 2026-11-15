"""Administrative theming accepts palette data without privileged path/CSS input."""
import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'shell/assets'))
import root_appearance


class RootAppearance(unittest.TestCase):
    def options(self):
        return dict(colours=dict(surface='101018', onSurface='eeeeee', surfaceContainer='202028',
                                 primary='aaccee', onPrimary='102030', outlineVariant='505060'),
                    mode='dark', antialias=True, hinting='slight', icons='Adwaita', cursor='Adwaita', cursorSize=24,
                    font='Adwaita Sans 11', qtFont='Adwaita Sans,11,-1,5,50,0,0,0,0,0',
                    controls={'side':'right','order':['minimize','maximize','close']})

    def test_rejects_paths_css_and_wrong_types(self):
        bad = [('icons', '../private'), ('cursor', "x'\nmalicious=true"), ('cursorSize', True),
               ('mode', 'system'), ('antialias', 'true')]
        for key, value in bad:
            request = self.options(); request[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError): root_appearance.validate(request)
        request = self.options(); request['colours']['surface'] = '@import url(file:///secret)'
        with self.assertRaises(ValueError): root_appearance.validate(request)

    def test_dark_and_light_publish_native_configs_without_user_bus(self):
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            for mode in ('dark', 'light'):
                request = self.options(); request['mode'] = mode
                with patch('root_appearance.subprocess.run') as run:
                    root_appearance.apply(request, home)
                self.assertIn('prefer-'+mode, run.call_args.kwargs['input'])
                self.assertEqual(run.call_args.args[0][:3], ['/usr/bin/dbus-run-session', '--', '/usr/bin/dconf'])
                for path in ('gtk-2.0/gtkrc', 'gtk-3.0/gtk.css', 'gtk-4.0/gtk.css',
                             'qt5ct/qt5ct.conf', 'qt6ct/qt6ct.conf', 'kdeglobals', 'hics/qtquickcontrols2.conf'):
                    self.assertTrue((home/'.config'/path).is_file(), path)
                self.assertIn(mode.title(), (home/'.config/hics/qtquickcontrols2.conf').read_text())

    def test_symlinked_root_config_is_not_written(self):
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)/'root'; home.mkdir()
            outside = Path(temp)/'outside'; outside.mkdir()
            (home/'.config').symlink_to(outside)
            with self.assertRaisesRegex(ValueError, 'Symlinked'):
                root_appearance.apply(self.options(), home)
            self.assertEqual(list(outside.iterdir()), [])
