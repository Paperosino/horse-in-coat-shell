"""Preserve existing preferences while adopting the documented hics paths."""
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('migrate_branding', ROOT/'shell/assets/migrate_branding.py')
migration = importlib.util.module_from_spec(spec)
spec.loader.exec_module(migration)
class BrandingMigration(unittest.TestCase):
    def test_old_data_is_preserved_and_migration_is_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            env = {key: str(base/key) for key in ('XDG_CONFIG_HOME','XDG_DATA_HOME','XDG_STATE_HOME','XDG_CACHE_HOME')}
            for value in env.values():
                old = Path(value)/'hyprstack'
                old.mkdir(parents=True)
                (old/'preferences.json').write_text('{"keep":true}')
            config = Path(env['XDG_CONFIG_HOME'])/'hypr'
            config.mkdir()
            file = config/'hyprland.lua'
            file.write_text('hl.exec("runhics-session")\n-- personal setting\n')
            with patch.dict(os.environ, env):
                migration.migrate()
                migration.migrate()
            for value in env.values():
                self.assertEqual((Path(value)/'hics/preferences.json').read_text(), '{"keep":true}')
                self.assertEqual((Path(value)/'hics/preferences.json').read_text(), '{"keep":true}')
            self.assertIn('hics-session', file.read_text())
            self.assertIn('personal setting', file.read_text())
            self.assertIn('runhics-session', file.with_suffix('.lua.before-hics').read_text())
    def test_existing_new_directory_is_not_replaced(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            (base/'hics').mkdir(); (base/'hyprstack').mkdir()
            with patch.dict(os.environ, {key:str(base) for key in ('XDG_CONFIG_HOME','XDG_DATA_HOME','XDG_STATE_HOME','XDG_CACHE_HOME')}):
                migration.migrate()
            self.assertFalse((base/'hics').is_symlink())
if __name__ == '__main__': unittest.main()
