"""No blind startup delay or retry of a failed in-process plugin initialization."""
import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('canvas_loader', ROOT/'shell/assets/load_canvas_plugin.py')
loader = importlib.util.module_from_spec(spec)
spec.loader.exec_module(loader)

class CanvasLoader(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.plugin = Path(self.temp.name)/'canvas.so'; self.plugin.touch()
    def test_already_loaded_never_reloads(self):
        with patch.object(loader, 'query', return_value='[{"name":"spatialoverview"}]') as q:
            self.assertTrue(loader.load(self.plugin)); self.assertEqual(q.call_count, 1)
    def test_ipc_without_complete_config_is_not_ready(self):
        with patch.object(loader, 'query', side_effect=['[]','[{}]','false','[]','[{}]','true','ok']) as q, patch.object(loader.time, 'sleep'):
            self.assertTrue(loader.load(self.plugin))
            self.assertEqual(sum(args[0][:2] == ('plugin', 'load') for args in q.call_args_list), 1)
    def test_failed_init_is_not_retried(self):
        with patch.object(loader, 'query', side_effect=['[]','[{}]','true','error: init failed']) as q:
            with self.assertRaisesRegex(RuntimeError, 'init failed'): loader.load(self.plugin)
            self.assertEqual(q.call_count, 4)
    def test_missing_optional_plugin(self):
        with patch.object(loader, 'query') as q:
            self.assertFalse(loader.load(self.plugin.with_name('absent'))); q.assert_not_called()
