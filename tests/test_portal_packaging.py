"""Verify portal source integrity checks and package activation boundaries."""
import hashlib
import importlib.util
import io
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('hics_portal_build',ROOT/'native/portal-runtime/build_backend.py')
build=importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)

class PortalPackaging(unittest.TestCase):
    def test_checksum_failure_prevents_source_extraction(self):
        with tempfile.TemporaryDirectory() as temp:
            sources={'bad':('https://invalid.example/source','0'*64)}
            with patch.object(build,'SOURCES',sources), patch.object(build.urllib.request,'urlopen',return_value=io.BytesIO(b'wrong')), patch('sys.argv',['build','--work',temp]):
                with self.assertRaisesRegex(ValueError,'checksum mismatch'):
                    build.main()
            self.assertFalse((Path(temp)/'bad-extract').exists())

    def test_source_archive_cannot_escape_work_directory(self):
        archive=io.BytesIO()
        with tarfile.open(fileobj=archive,mode='w:gz') as tar:
            entry=tarfile.TarInfo('../escape');entry.size=1;tar.addfile(entry,io.BytesIO(b'x'))
        blob=archive.getvalue()
        with tempfile.TemporaryDirectory() as parent:
            work=Path(parent)/'work'
            with patch.object(build,'SOURCES',{'bad':('https://invalid.example/source',hashlib.sha256(blob).hexdigest())}), patch.object(build.urllib.request,'urlopen',return_value=io.BytesIO(blob)), patch('sys.argv',['build','--work',str(work)]):
                with self.assertRaises(tarfile.TarError):build.main()
            self.assertFalse((Path(parent)/'escape').exists())

    def test_update_and_package_activate_only_existing_backend(self):
        update=(ROOT/'distribution/update.py').read_text()
        self.assertNotIn('60-hics-portal-backend.conf',update)
        manifest=(ROOT/'packaging/arch/PKGBUILD').read_text()
        self.assertIn('60-hics-portal-backend.conf',manifest)
        override=(ROOT/'distribution/systemd/user/xdg-desktop-portal-hyprland.service.d/60-hics-portal-backend.conf').read_text()
        self.assertIn('ExecStart=/usr/share/hics/portal/xdg-desktop-portal-hyprland',override)

if __name__=='__main__':unittest.main()
