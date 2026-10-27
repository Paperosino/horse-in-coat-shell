"""Qt package overlay integrity, aliases and non-truncating publication."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('hics_qt_overlay',ROOT/'distribution/apply_qt_runtime_patches.py')
overlay=importlib.util.module_from_spec(spec);spec.loader.exec_module(overlay)

class QtOverlayTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name);self.source=self.base/'overlay';self.root=self.base/'bundle'
        self.files={'lib/libQt6Core.so.6.12.0':b'new core','plugins/platforms/libqwayland.so':b'new platform','licenses/md4c.txt':b'license'}
        for name,data in self.files.items():
            p=self.source/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
        (self.source/'lib/libQt6Core.so.6').symlink_to('libQt6Core.so.6.12.0')
        (self.source/'lib/qt6').mkdir();(self.source/'lib/qt6/plugins').symlink_to('../../plugins')
        self.metadata={'qtVersion':'6.12.0','files':{name:hashlib.sha256(data).hexdigest() for name,data in self.files.items()},
            'symlinks':{'lib/libQt6Core.so.6':'libQt6Core.so.6.12.0','lib/qt6/plugins':'../../plugins'}}
        self.save()
        (self.root/'bin').mkdir(parents=True);(self.root/'lib').mkdir()
        (self.root/'lib/libQt6Core.so.6.12.0').write_bytes(b'old core')

    def save(self):
        (self.source/'hics-qt-patches.json').write_text(json.dumps(self.metadata))

    def test_publication_preserves_old_inode_and_unmodified_plugins(self):
        old=self.root/'lib/libQt6Core.so.6.12.0'
        untouched=self.root/'lib/qt6/plugins/imageformats/existing.so';untouched.parent.mkdir(parents=True);untouched.write_bytes(b'keep')
        with old.open('rb') as reader:
            overlay.apply(self.source,self.root)
            self.assertEqual(reader.read(),b'old core')
        self.assertEqual(old.read_bytes(),b'new core');self.assertEqual(untouched.read_bytes(),b'keep')
        self.assertTrue((self.root/'lib/qt6/plugins').is_dir());self.assertFalse((self.root/'lib/qt6/plugins').is_symlink())
        self.assertEqual((self.root/'licenses/qt-patches/md4c.txt').read_bytes(),b'license')
        overlay.read(self.root)

    def test_corrupt_plugin_is_rejected_before_core_is_replaced(self):
        (self.source/'plugins/platforms/libqwayland.so').write_bytes(b'corrupted')
        with self.assertRaisesRegex(ValueError,'checksum mismatch'):overlay.apply(self.source,self.root)
        self.assertEqual((self.root/'lib/libQt6Core.so.6.12.0').read_bytes(),b'old core')

    def test_matching_manifest_cannot_authorize_alias_outside_overlay(self):
        p=self.source/'lib/libQt6Core.so.6';p.unlink();p.symlink_to('../../outside')
        self.metadata['symlinks']['lib/libQt6Core.so.6']='../../outside';self.save()
        with self.assertRaisesRegex(ValueError,'alias mismatch'):overlay.apply(self.source,self.root)

    def test_manifest_traversal_is_rejected(self):
        self.metadata['files']['../outside']='not a checksum';self.save()
        with self.assertRaisesRegex(ValueError,'Unsafe'):overlay.apply(self.source,self.root)

    def test_packaged_alias_corruption_is_detected(self):
        overlay.apply(self.source,self.root)
        p=self.root/'lib/libQt6Core.so.6';p.unlink();p.symlink_to('missing.so')
        with self.assertRaisesRegex(ValueError,'alias mismatch'):overlay.read(self.root)

    def test_fifo_manifest_is_rejected_without_waiting_for_writer(self):
        p=self.source/'hics-qt-patches.json';p.unlink();os.mkfifo(p)
        with self.assertRaisesRegex(ValueError,'regular file'):overlay.read(self.source)

    def test_manifest_symlink_is_not_followed(self):
        p=self.source/'hics-qt-patches.json';p.unlink();p.symlink_to(self.base/'outside')
        with self.assertRaises(OSError):overlay.read(self.source)
