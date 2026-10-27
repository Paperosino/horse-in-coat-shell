"""The real Arch package() refuses an incomplete private runtime."""
import os, shutil, subprocess, tempfile, unittest, hashlib, json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class PackagePayload(unittest.TestCase):
 def setUp(self):
  tmp=tempfile.TemporaryDirectory(prefix='hics package payload ');self.addCleanup(tmp.cleanup);self.base=Path(tmp.name)
  self.source=self.base/'fixture';self.package=self.base/'pkg';self.start=self.base/'build';(self.start/'src/hics').mkdir(parents=True)
  self.payload=('qs/bin/hics-qs','qs/lib/libQt6Core.so.6','qs/lib/libQt6Concurrent.so.6','qs/lib/libjemalloc.so.2','qs/licenses/jemalloc-BSD-2-Clause','qs/hics-qt-patches.json','qs/hics-quickshell-patches.json','shell/shell.qml','shell/recovery/shell.qml')
  for name in self.payload:
   p=self.source/'usr/share/hics'/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('fixture');p.chmod(0o755 if name.endswith('hics-qs') else 0o644)
  helper=self.start/'src/hics/distribution';helper.mkdir()
  shutil.copy2(ROOT/'distribution/apply_qt_runtime_patches.py',helper/'apply_qt_runtime_patches.py')
  shutil.copy2(ROOT/'distribution/apply_quickshell_patches.py',helper/'apply_quickshell_patches.py')
  shutil.copytree(ROOT/'distribution/patches',helper/'patches')
  root=self.source/'usr/share/hics/qs'
  (root/'hics-qt-patches.json').write_text(json.dumps({'qtVersion':'6.12.0','files':{
   'lib/libQt6Core.so.6':hashlib.sha256((root/'lib/libQt6Core.so.6').read_bytes()).hexdigest()},'symlinks':{}}))
  patches=tuple(p.name for p in sorted((helper/'patches').glob('quickshell-v0.3.2-*.patch')))
  (root/'hics-quickshell-patches.json').write_text(json.dumps({'version':'0.3.2','archiveSha256':'946a27e2a276917a03c1079e5c60971af84ece73088c3661dee455d92eb420f7','patches':{p:hashlib.sha256((helper/'patches'/p).read_bytes()).hexdigest() for p in patches},'executableSha256':hashlib.sha256((root/'bin/hics-qs').read_bytes()).hexdigest(),'allocator':{'kind':'jemalloc','path':'lib/libjemalloc.so.2','sha256':hashlib.sha256((root/'lib/libjemalloc.so.2').read_bytes()).hexdigest()}}))
 def run_package(self):
  if self.package.exists():shutil.rmtree(self.package)
  self.package.mkdir()
  env=dict(os.environ,startdir=str(self.start),pkgdir=str(self.package),HICS_PAYLOAD_FIXTURE=str(self.source),HICS_VALIDATED=str(self.base/'validated'))
  script='''source "$1"
cmake() { cp -a "$HICS_PAYLOAD_FIXTURE/." "$pkgdir/"; }
python() { if [[ $1 == distribution/apply_qt_runtime_patches.py || $1 == distribution/apply_quickshell_patches.py ]]; then command python "$@"; else touch "$HICS_VALIDATED"; fi; }
error() { printf '%s\\n' "$*" >&2; }
package
'''
  return subprocess.run(['bash','-e','-c',script,'_',str(ROOT/'packaging/arch/PKGBUILD')],env=env,capture_output=True,text=True,timeout=5)
 def test_each_missing_runtime_component_stops_packaging_before_native_validation(self):
  for name in self.payload:
   with self.subTest(component=name):
    p=self.source/'usr/share/hics'/name;data=p.read_bytes();mode=p.stat().st_mode;p.unlink()
    result=self.run_package();self.assertNotEqual(result.returncode,0);self.assertIn(name,result.stderr);self.assertFalse((self.base/'validated').exists())
    p.write_bytes(data);p.chmod(mode)
 def test_complete_payload_reaches_native_validation_but_nonexecutable_runtime_does_not(self):
  result=self.run_package();self.assertEqual(result.returncode,0,result.stderr);(self.base/'validated').unlink()
  (self.source/'usr/share/hics/qs/bin/hics-qs').chmod(0o644)
  result=self.run_package();self.assertNotEqual(result.returncode,0);self.assertIn('not executable',result.stderr);self.assertFalse((self.base/'validated').exists())
 def test_corrupt_qt_payload_stops_before_native_validation(self):
  (self.source/'usr/share/hics/qs/lib/libQt6Core.so.6').write_text('corrupt')
  result=self.run_package();self.assertNotEqual(result.returncode,0);self.assertIn('checksum mismatch',result.stderr);self.assertFalse((self.base/'validated').exists())
if __name__=='__main__' :unittest.main()
