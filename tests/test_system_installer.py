"""Validate the privileged helper's installation plan without writing host files."""
import importlib.util,tempfile,unittest,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('system_installer',ROOT/'distribution/install_system_helper.py')
installer=importlib.util.module_from_spec(spec);spec.loader.exec_module(installer)
class SystemInstaller(unittest.TestCase):
 def test_service_never_executes_user_owned_build(self):
  with tempfile.TemporaryDirectory() as directory:
   prefix=Path(directory);(prefix/'bin').mkdir()
   for name in ('hyprstack-systemd','hyprstack-systemctl'):(prefix/'bin'/name).write_bytes(b'fixture')
   plan={str(path):(content,mode) for path,content,mode in installer.deployment(prefix)}
   self.assertEqual(len(plan),6)
   for path,(content,mode) in plan.items():
    self.assertNotIn(directory,path)
    if path.endswith('.service'):
     self.assertNotIn(directory,content.decode());self.assertIn('/usr/local/bin/hyprstack-systemd',content.decode())
    self.assertEqual(mode,0o755 if path.startswith('/usr/local/bin/') else 0o644)
 def test_package_wires_system_service_post_install(self):
  pkg=(ROOT/'packaging/arch/PKGBUILD').read_text()
  script=(ROOT/'packaging/arch/build-package.sh').read_text()
  self.assertIn('install=hic-shell.install',pkg);self.assertIn('"$here/hic-shell.install"',script)

 def test_fresh_checkout_includes_installer_dependencies(self):
  if not (ROOT/'.git').exists():self.skipTest('archive checkout')
  required=['native/system/CMakeLists.txt','third_party/phantomat/main.cpp','distribution/install_system_helper.py','distribution/native_plugins.py','shell/assets/gtk_theme.py','packaging/arch/hic-shell.install','tests/fixtures/virtual-pointer.c']
  result=subprocess.run(['git','check-ignore',*required],cwd=ROOT,text=True,capture_output=True)
  self.assertEqual(result.stdout,'',result.stdout)
