"""Resolve real transitive ELF dependencies and converge on repeated assembly."""
import hashlib
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class RuntimeDependenciesTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='hics dependency closure ')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source = self.root / 'source libraries'
        self.source.mkdir()
        self.output = self.root / 'bundle libraries'
        self.output.mkdir()
        (self.source / 'leaf.c').write_text('int fixture_leaf(void) { return 42; }\n')
        (self.source / 'middle.c').write_text('extern int fixture_leaf(void); int fixture_middle(void) { return fixture_leaf(); }\n')
        (self.source / 'main.c').write_text('extern int fixture_middle(void); int main(void) { return fixture_middle() != 42; }\n')
        commands = [
            ['cc', '-shared', '-fPIC', 'leaf.c', '-Wl,-soname,libfixture-leaf.so', '-o', 'libfixture-leaf.so'],
            ['cc', '-shared', '-fPIC', 'middle.c', '-L.', '-lfixture-leaf',
             '-Wl,-soname,libfixture-middle.so', '-Wl,-rpath,$ORIGIN', '-o', 'libfixture-middle.so'],
            ['cc', 'main.c', '-L.', '-lfixture-middle', '-Wl,-rpath,' + str(self.source), '-o', 'fixture'],
        ]
        for command in commands:
            subprocess.run(command, cwd=self.source, check=True, capture_output=True, timeout=15)

    def assemble(self):
        env = dict(os.environ, qs_bin=str(self.source / 'fixture'), lib_dir=str(self.output))
        return subprocess.run(['bash', '-c', 'set -euo pipefail; source "$1"; fixpoint',
                               'fixture', str(ROOT / 'distribution/runtime-dependencies.sh')],
                              env=env, capture_output=True, text=True, timeout=10)

    def test_transitive_closure_is_complete_and_idempotent(self):
        first = self.assemble()
        self.assertEqual(first.returncode, 0, first.stderr)
        expected = {'libfixture-leaf.so', 'libfixture-middle.so'}
        self.assertEqual({p.name for p in self.output.iterdir()}, expected)
        hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in self.output.iterdir()}
        second = self.assemble()
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(second.stdout, '')
        self.assertEqual(hashes, {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in self.output.iterdir()})

    def test_unresolved_dependency_fails_instead_of_shipping_partial_runtime(self):
        (self.source / 'libfixture-leaf.so').unlink()
        result = self.assemble()
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn('missing dependency libfixture-leaf.so', result.stderr)

    @unittest.skipIf(os.geteuid() == 0, 'Root bypasses directory write permissions')
    def test_copy_failure_is_not_mistaken_for_a_stable_closure(self):
        self.output.chmod(0o555)
        self.addCleanup(lambda: self.output.chmod(0o755))
        result = self.assemble()
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(list(self.output.iterdir()), [])


if __name__ == '__main__':
    unittest.main()
