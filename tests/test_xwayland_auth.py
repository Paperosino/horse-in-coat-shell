"""Cookie handling must preserve session isolation and never expose secrets in argv."""
import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('xwayland_auth', ROOT/'shell/assets/xwayland_auth.py')
auth = importlib.util.module_from_spec(spec)
spec.loader.exec_module(auth)


class XwaylandAuth(unittest.TestCase):
    def test_real_xauth_cookies_are_private_and_per_session(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            launcher = base/'data/xwayland/Xwayland'
            launcher.parent.mkdir(parents=True)
            launcher.touch(mode=0o755)
            with patch.dict(os.environ, {'XDG_RUNTIME_DIR': str(base)}):
                first = auth.prepare(base/'data')
                second = auth.prepare(base/'data')
            self.assertNotEqual(first['XAUTHORITY'], second['XAUTHORITY'])
            for environment in (first, second):
                with patch.dict(os.environ, environment):
                    args = auth.server_arguments([':37', '-rootless', '-listenfd', '8'])
                self.assertEqual(args[-4:], ['-auth', environment['XAUTHORITY'], '-nolisten', 'tcp'])
                self.assertEqual(Path(environment['XAUTHORITY']).stat().st_mode & 0o777, 0o600)
                result = subprocess.run(['xauth', '-f', environment['XAUTHORITY'], 'list'], capture_output=True, text=True, check=True)
                self.assertIn('MIT-MAGIC-COOKIE-1', result.stdout)
                cookie = result.stdout.split()[-1]
                self.assertEqual(len(cookie), 32)
                self.assertNotIn(cookie, ' '.join(args))

    def test_unsafe_file_and_bad_display_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            file = Path(temporary)/'authority'
            file.touch(mode=0o644)
            with patch.dict(os.environ, {'HICS_XWAYLAND_AUTHORITY': str(file)}):
                with self.assertRaisesRegex(ValueError, 'Unsafe'):
                    auth.server_arguments([':0'])
                file.chmod(0o600)
                with self.assertRaisesRegex(ValueError, 'Unexpected'):
                    auth.server_arguments([':0;bad'])
                with self.assertRaisesRegex(ValueError, 'duplicate'):
                    auth.server_arguments([':0', '-auth', '/other'])

    def test_unmanaged_launch_passes_through(self):
        with patch.dict(os.environ):
            os.environ.pop('HICS_XWAYLAND_AUTHORITY', None)
            self.assertEqual(auth.server_arguments([':9']), [':9'])
