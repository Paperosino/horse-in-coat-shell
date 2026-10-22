"""Capture adapter startup must be idempotent and report hyprctl failures."""
import importlib.util
import io
import os
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("capture_session_runner", Path(__file__).resolve().parents[1] / "shell/assets/session_runner.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class CaptureLoaderTests(unittest.TestCase):
    def invoke(self, replies):
        with patch.dict(os.environ, {"HICS_DATA_DIR": "/test/hics"}), patch.object(runner.Path, "is_file", return_value=True), patch.object(runner.shutil, "which", return_value="/usr/bin/hyprctl"), patch.object(runner.subprocess, "run", side_effect=replies) as run, patch("sys.stderr", new_callable=io.StringIO) as errors:
            runner.load_capture_plugin()
            return run.call_args_list, errors.getvalue()

    def test_loaded_adapter_is_not_reloaded(self):
        calls, errors = self.invoke([subprocess.CompletedProcess([], 0, '[{"name":"hics-capture"}]', '')])
        self.assertEqual(len(calls), 1)
        self.assertFalse(errors)

    def test_missing_adapter_is_loaded_from_shell_data(self):
        calls, errors = self.invoke([subprocess.CompletedProcess([], 0, '[]', ''), subprocess.CompletedProcess([], 0, 'ok\n', '')])
        self.assertEqual(calls[1].args[0], ['hyprctl', 'plugin', 'load', '/test/hics/native/hics-capture.so'])
        self.assertFalse(errors)

    def test_hyprctl_reports_plugin_failure_with_zero_exit_status(self):
        _, errors = self.invoke([subprocess.CompletedProcess([], 0, '[]', ''), subprocess.CompletedProcess([], 0, 'Plugin could not be loaded: ABI mismatch', '')])
        self.assertIn('ABI mismatch', errors)

    def test_compositor_timeout_does_not_stop_shell(self):
        _, errors = self.invoke([subprocess.TimeoutExpired('hyprctl', 5)])
        self.assertIn('Unable to load', errors)
