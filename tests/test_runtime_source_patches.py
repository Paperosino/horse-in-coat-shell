"""Source patch checks must never guess that an unapplied patch was reversed."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]

def module(name, file):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'distribution' / file)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result

QS = module('qs_patches', 'apply_quickshell_patches.py')
QT = module('qt_patches', 'build_qt_runtime_patches.py')
DIFF = '--- a/file.cpp\n+++ b/file.cpp\n@@ -1,2 +1,2 @@\n line\n-before\n+after\n'

class SourcePatchTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='hics source patch ')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source = self.root / 'source'
        self.source.mkdir()
        (self.source / 'CMakeLists.txt').write_text('project(quickshell VERSION "0.3.2" LANGUAGES CXX)\n')
        (self.source / 'file.cpp').write_text('line\nbefore\n')
        patches = self.root / 'distribution/patches'
        patches.mkdir(parents=True)
        self.patch = patches / 'fixture.patch'
        self.patch.write_text(DIFF)

    def test_qs_check_rejects_unapplied_source_without_mutating_it(self):
        with patch.object(QS, 'ROOT', self.root), patch.object(QS, 'PATCHES', ('fixture.patch',)):
            with self.assertRaisesRegex(ValueError, 'missing'):
                QS.source_check(self.source)
        self.assertEqual((self.source / 'file.cpp').read_text(), 'line\nbefore\n')

    def test_qs_apply_is_real_and_second_apply_does_not_reverse_it(self):
        with patch.object(QS, 'ROOT', self.root), patch.object(QS, 'PATCHES', ('fixture.patch',)):
            QS.source_check(self.source, apply=True)
            self.assertEqual((self.source / 'file.cpp').read_text(), 'line\nafter\n')
            QS.source_check(self.source, apply=True)
            QS.source_check(self.source)
        self.assertEqual((self.source / 'file.cpp').read_text(), 'line\nafter\n')

    def test_qt_apply_is_real_and_second_apply_does_not_reverse_it(self):
        QT.apply_source_patch(self.source, self.patch)
        self.assertEqual((self.source / 'file.cpp').read_text(), 'line\nafter\n')
        QT.apply_source_patch(self.source, self.patch)
        self.assertEqual((self.source / 'file.cpp').read_text(), 'line\nafter\n')

    def test_qs_rejects_unaudited_source_version(self):
        (self.source / 'CMakeLists.txt').write_text('project(quickshell VERSION "0.3.3")\n')
        with self.assertRaisesRegex(ValueError, '0.3.2'):
            QS.source_check(self.source, apply=True)

class QtOverlayPlaceholderTests(unittest.TestCase):
    def test_only_empty_ninja_placeholder_is_removed(self):
        with tempfile.TemporaryDirectory(prefix='hics Qt placeholder ') as directory:
            root = Path(directory)
            stage = root / 'overlay'
            stage.mkdir()
            argv = ['builder', '--work', str(root/'work'), '--stage', str(stage)]
            with patch('sys.argv', argv), patch.object(QT, 'PATCHES', {}), \
                    patch.object(QT, 'sha', return_value='0'*64), \
                    patch.object(QT, 'header_digest', return_value='1'*64), \
                    patch.object(QT.subprocess, 'check_output', side_effect=['6.12.0\n', str(root/'headers')+'\n']), \
                    patch.object(QT, 'fetch', side_effect=RuntimeError('reached source fetch')):
                with self.assertRaisesRegex(RuntimeError, 'reached source fetch'):
                    QT.main()
            self.assertFalse(stage.exists())
            stage.mkdir()
            marker = stage/'preserve.txt'
            marker.write_text('existing incomplete output')
            with patch('sys.argv', argv), patch.object(QT, 'PATCHES', {}), \
                    patch.object(QT, 'sha', return_value='0'*64), \
                    patch.object(QT, 'header_digest', return_value='1'*64), \
                    patch.object(QT.subprocess, 'check_output', side_effect=['6.12.0\n', str(root/'headers')+'\n']):
                with self.assertRaises(FileNotFoundError):
                    QT.main()
            self.assertEqual(marker.read_text(), 'existing incomplete output')

class RuntimeProvenanceTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='hics QS provenance ')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        (self.root / 'bin').mkdir()
        self.binary = self.root / 'bin/hics-qs'
        self.binary.write_bytes(b'fixture executable')
        self.binary.chmod(0o755)
        self.manifest = self.root / QS.MANIFEST
        self.data = {'version':'0.3.2','archiveSha256':QS.ARCHIVE_SHA256,
                     'patches':QS.patch_hashes(),'executableSha256':hashlib.sha256(self.binary.read_bytes()).hexdigest()}
        self.manifest.write_text(json.dumps(self.data))

    def test_correct_binary_and_patch_manifest(self):
        QS.verify(self.root)

    def set_allocator(self):
        (self.root / 'lib').mkdir()
        library = self.root / 'lib/libjemalloc.so.2'
        library.write_bytes(b'allocator image')
        self.data['allocator'] = {'kind':'jemalloc','path':'lib/libjemalloc.so.2','sha256':QS.sha(library)}
        self.manifest.write_text(json.dumps(self.data))
        return library

    def test_allocator_is_attested_and_tampering_is_rejected(self):
        library = self.set_allocator()
        QS.verify(self.root)
        library.write_bytes(b'changed allocator image')
        with self.assertRaisesRegex(ValueError, 'Allocator checksum'):
            QS.verify(self.root)

    def test_release_gate_rejects_legacy_allocator_but_diagnostics_accept_it(self):
        QS.verify(self.root)
        with self.assertRaisesRegex(ValueError, 'jemalloc provenance'):
            QS.verify(self.root, require_jemalloc=True)
        self.set_allocator()
        QS.verify(self.root, require_jemalloc=True)

    def test_allocator_cannot_resolve_outside_bundle(self):
        library = self.set_allocator()
        external = self.root.parent / (self.root.name + '-external.so')
        external.write_bytes(library.read_bytes())
        self.addCleanup(lambda: external.unlink(missing_ok=True))
        library.unlink()
        library.symlink_to(external)
        with self.assertRaisesRegex(ValueError, 'inside the runtime'):
            QS.verify(self.root)

    def test_allocator_manifest_path_cannot_escape(self):
        self.set_allocator()
        self.data['allocator']['path'] = '../external.so'
        self.manifest.write_text(json.dumps(self.data))
        with self.assertRaisesRegex(ValueError, 'Unsupported allocator'):
            QS.verify(self.root)

    def test_changed_binary_is_rejected(self):
        self.binary.write_bytes(b'old cached QS')
        with self.assertRaisesRegex(ValueError, 'checksum'):
            QS.verify(self.root)

    def test_wrong_patch_set_is_rejected(self):
        self.data['patches'] = {}
        self.manifest.write_text(json.dumps(self.data))
        with self.assertRaisesRegex(ValueError, 'provenance'):
            QS.verify(self.root)

    def test_symlink_manifest_is_not_followed(self):
        self.manifest.rename(self.root / 'actual.json')
        self.manifest.symlink_to('actual.json')
        with self.assertRaises(OSError):
            QS.verify(self.root)

    def test_fifo_manifest_cannot_block_the_packager(self):
        self.manifest.unlink()
        os.mkfifo(self.manifest)
        with self.assertRaisesRegex(ValueError, 'regular'):
            QS.verify(self.root)

    def test_executable_alias_is_rejected(self):
        self.binary.rename(self.root / 'bin/actual')
        self.binary.symlink_to('actual')
        with self.assertRaisesRegex(ValueError, 'regular executable'):
            QS.verify(self.root)

if __name__ == '__main__':
    unittest.main()
