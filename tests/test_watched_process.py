"""Nonblocking replacement, forced stop, reentrant teardown and shutdown reap."""
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]

class WatchedProcessTests(unittest.TestCase):
    def test_lifetimes_under_asan(self):
        with tempfile.TemporaryDirectory(prefix='hics-watched-process-') as d:
            binary = Path(d) / 'probe'
            flags = shlex.split(subprocess.check_output(['pkg-config', '--cflags', '--libs', 'Qt6Core'], text=True))
            subprocess.run(['c++', '-std=c++20', '-fPIC', '-fsanitize=address', '-fno-omit-frame-pointer', '-g',
                str(ROOT / 'tests/fixtures/watched-process-lifetime.cpp'), '-I' + str(ROOT / 'shell/plugin/include'),
                *flags, '-o', str(binary)], check=True, capture_output=True, text=True, timeout=30)
            env = dict(os.environ, ASAN_OPTIONS='detect_leaks=1:halt_on_error=1')
            env.pop('LSAN_OPTIONS', None)
            result = subprocess.run([str(binary)], env=env, capture_output=True, text=True, timeout=15)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertNotIn('Destroyed while process', result.stderr)
            self.assertIn('WATCHED_PROCESS_COMPLETE', result.stdout)
            child = int(result.stdout.split('FINAL_CHILD ')[1].splitlines()[0])
            with self.assertRaises(ProcessLookupError):
                os.kill(child, 0)

if __name__ == '__main__':
    unittest.main()
