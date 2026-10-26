"""Real session-bus LauncherEntry updates, partial updates and sender teardown."""
import os,shlex,shutil,subprocess,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class ApplicationBadgesTests(unittest.TestCase):
 def test_dbus_lifecycle(self):
  with tempfile.TemporaryDirectory(prefix='hics-badges-test-') as tmp:
   base=Path(tmp);src=ROOT/'shell/plugin/src/Hyprstack/Services';moc=shutil.which('moc6') or '/usr/lib/qt6/moc'
   subprocess.run([moc,str(src/'applicationbadges.hpp'),'-o',str(base/'moc.cpp')],check=True,capture_output=True)
   flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','Qt6Core','Qt6DBus','Qt6Qml'],text=True))
   build=subprocess.run(['c++','-std=c++20','-fPIC',str(ROOT/'tests/fixtures/application-badges.cpp'),str(src/'applicationbadges.cpp'),str(base/'moc.cpp'),'-I'+str(src),*flags,'-o',str(base/'test')],capture_output=True,text=True)
   self.assertEqual(build.returncode,0,build.stderr)
   result=subprocess.run(['dbus-run-session','--',str(base/'test')],capture_output=True,text=True,timeout=5)
   self.assertEqual(result.returncode,0,result.stdout+result.stderr)
