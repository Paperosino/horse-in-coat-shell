import contextlib
import io
import os
from pathlib import Path
import shutil
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "distribution"))
import update


class UpdateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="hyprstack update ")
        self.home = Path(self.temp.name)
        self.environment = patch.dict(os.environ, HOME=str(self.home), XDG_CONFIG_HOME=str(self.home / "config"),
            XDG_DATA_HOME=str(self.home / "data"), XDG_STATE_HOME=str(self.home / "state"),
            HYPRLAND_INSTANCE_SIGNATURE="", HYPRSTACK_DATA_DIR="")
        self.environment.start()
        self.manager = update.Update(self.home)
        self.stage = self.home / "stage"
        (self.stage / "bin").mkdir(parents=True)
        (self.stage / "bin/hyprstack").write_text("new executable")
        (self.stage / "bin/hyprstack").chmod(0o755)
        (self.stage / "share/hyprstack/native").mkdir(parents=True)
        (self.stage / "share/hyprstack/native/hyprstack-bars.so").write_text("new native module")
        self.manager.staging = self.stage
        self.output = contextlib.ExitStack()
        self.output.enter_context(contextlib.redirect_stdout(io.StringIO()))
        self.output.enter_context(contextlib.redirect_stderr(io.StringIO()))

    def tearDown(self):
        self.output.close()
        self.environment.stop()
        self.temp.cleanup()

    def existing(self):
        targets = {
            self.manager.bin / "hyprstack": "old executable",
            self.manager.data / "hyprstack/native/hyprstack-bars.so": "old native module",
            self.manager.config / "hypr/hyprland.lua": "old compositor config",
            self.manager.config / "hypr/scheme/current.lua": "personal theme",
            self.manager.config / "hyprstack/hypr-user.lua": "old entry",
            self.manager.config / "hyprstack/hypr-vars.lua": "personal programs",
            self.manager.config / "hyprstack/monitors.lua": "personal monitors",
            self.manager.config / "hyprstack/local.lua": "personal bindings",
            self.manager.config / "hyprstack/shell.json": '{"personal":true}',
            self.manager.config / "hypr/unrelated.txt": "unrelated file",
        }
        for path, content in targets.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
        return targets

    def deploy(self):
        update.validate_destinations(self.manager, list(self.manager.plan()))
        self.manager.transaction("install")

    def test_manual_install_upgrade_preserves_preferences_theme_and_unrelated_files(self):
        previous = self.existing()
        # Existing mappings keep their old inode while replacements are atomic.
        with (self.manager.data / "hyprstack/native/hyprstack-bars.so").open() as loaded:
            self.deploy()
            self.assertEqual(loaded.read(), "old native module")
        for path, content in previous.items():
            if path.name in ("hyprland.lua", "hypr-user.lua", "hyprstack", "hyprstack-bars.so"):
                self.assertNotEqual(path.read_text(), content)
            else:
                self.assertEqual(path.read_text(), content)
        self.assertTrue((self.manager.bin / "hyprstack").stat().st_mode & 0o111)

    def test_repeat_update_is_idempotent(self):
        self.existing()
        self.deploy()
        ledger, latest = self.manager.manifest.read_bytes(), self.manager.latest.read_bytes()
        self.deploy()
        self.assertEqual(self.manager.manifest.read_bytes(), ledger)
        self.assertEqual(self.manager.latest.read_bytes(), latest)

    def test_rollback_restores_program_module_and_managed_configuration(self):
        before = self.existing()
        self.deploy()
        update.rollback(self.manager)
        for path, content in before.items():
            self.assertEqual(path.read_text(), content)
        self.assertFalse(self.manager.manifest.exists())
        with self.assertRaisesRegex(ValueError, "уже отменено"):
            update.rollback(self.manager)

    def test_write_failure_rolls_back_partial_update(self):
        before = self.existing()
        ensure = self.manager.ensure_parents
        count = 0
        def fail(path, created):
            nonlocal count
            count += 1
            if count == 4:
                raise OSError("disk full")
            return ensure(path, created)
        with patch.object(self.manager, "ensure_parents", side_effect=fail):
            with self.assertRaisesRegex(OSError, "disk full"):
                self.deploy()
        for path, content in before.items():
            self.assertEqual(path.read_text(), content)
        self.assertFalse(self.manager.pending.exists())
        self.assertFalse(self.manager.manifest.exists())

    def test_symlinked_config_directory_is_rejected_before_deployment(self):
        self.manager.config.mkdir()
        original = self.home / "dotfiles"
        original.mkdir()
        (self.manager.config / "hypr").symlink_to(original, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "ссылкой"):
            update.validate_destinations(self.manager, list(self.manager.plan()))
        self.assertEqual(list(original.iterdir()), [])

    def test_symlink_leaf_is_replaced_without_writing_its_target_and_restored(self):
        target = self.home / "original.lua"
        target.write_text("original target")
        entry = self.manager.config / "hypr/hyprland.lua"
        entry.parent.mkdir(parents=True)
        entry.symlink_to(target)
        self.deploy()
        self.assertFalse(entry.is_symlink())
        self.assertEqual(target.read_text(), "original target")
        update.rollback(self.manager)
        self.assertTrue(entry.is_symlink())

    def test_dry_run_does_not_create_directories_or_pull(self):
        with patch.object(update, "pull_sources") as pull:
            self.assertEqual(update.main(["--dry-run"]), 0)
        pull.assert_not_called()
        for directory in (self.manager.config, self.manager.data, self.manager.state, self.manager.bin):
            self.assertFalse(directory.exists())

    def test_running_session_rejects_update_before_git_or_build(self):
        with patch.object(update, "active_compositors", return_value=["running"]), \
             patch.object(update, "pull_sources") as pull, patch.object(update, "build") as build:
            self.assertEqual(update.main([]), 1)
        pull.assert_not_called()
        build.assert_not_called()
        self.assertFalse(self.manager.root.exists())

    def test_empty_instances_output_in_hyprland_0562(self):
        with patch.object(update, "capture", return_value="\n]\n"):
            self.assertEqual(update.active_compositors(self.manager), [])

    def test_failed_build_leaves_installed_files_untouched(self):
        before = self.existing()
        with patch.object(update, "active_compositors", return_value=[]), \
             patch.object(update, "preflight", return_value={"abiHash":"test"}), \
             patch.object(update, "build", side_effect=OSError("build failed")):
            self.assertEqual(update.main(["--no-pull"]), 1)
        for path, content in before.items():
            self.assertEqual(path.read_text(), content)

    def test_session_started_during_build_prevents_deployment(self):
        before = self.existing()
        def stage(command, **kwargs):
            destination = Path(kwargs["env"]["DESTDIR"]) / str(self.home / ".local").lstrip("/")
            shutil.copytree(self.stage, destination)
            return SimpleNamespace(returncode=0)
        with patch.object(update, "require_logged_out", side_effect=[None, ValueError("new session")]), \
             patch.object(update, "preflight", return_value={"abiHash":"test"}), \
             patch.object(update, "build", return_value=self.home / "build"), \
             patch.object(update.subprocess, "run", side_effect=stage):
            self.assertEqual(update.main(["--no-pull"]), 1)
        for path, content in before.items():
            self.assertEqual(path.read_text(), content)

    def test_dirty_sources_are_not_pulled_or_stashed(self):
        (self.home / ".git").mkdir()
        with patch.object(update, "ROOT", self.home), \
             patch.object(update.subprocess, "run", return_value=SimpleNamespace(stdout=" M local.py")) as run:
            with self.assertRaisesRegex(ValueError, "локальные изменения"):
                update.pull_sources()
        self.assertEqual(run.call_count, 1)
        self.assertEqual(run.call_args.args[0], ["git", "status", "--porcelain"])

    def test_lock_rejects_concurrent_updates(self):
        with update.installation_lock(self.manager):
            with self.assertRaisesRegex(ValueError, "уже выполняется"):
                with update.installation_lock(self.manager):
                    pass


if __name__ == "__main__":
    unittest.main()
