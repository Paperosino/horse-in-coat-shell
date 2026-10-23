"""A shell reload must preserve applications in its original process group."""
import importlib.util,os,signal,subprocess,sys,tempfile,time,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('session_restart_runner',ROOT/'shell/assets/session_runner.py');runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)
class SessionRestartTests(unittest.TestCase):
 def fixture(self,root):
  marker=root/'child'
  script='import subprocess,pathlib,time; p=subprocess.Popen(["sleep","120"]);pathlib.Path('+repr(str(marker))+').write_text(str(p.pid));time.sleep(120)'
  parent=subprocess.Popen([sys.executable,'-c',script],start_new_session=True)
  end=time.monotonic()+3
  while not marker.exists() and time.monotonic()<end:time.sleep(.01)
  self.assertTrue(marker.exists());return parent,int(marker.read_text())
 def alive(self,pid):
  try:return Path(f'/proc/{pid}/stat').read_text().rsplit(')',1)[1].split()[0]!='Z'
  except FileNotFoundError:return False
 def cleanup(self,parent):
  try:os.killpg(parent.pid,signal.SIGKILL)
  except ProcessLookupError:pass
  parent.wait()
 def test_restart_stops_shell_but_preserves_inherited_application(self):
  with tempfile.TemporaryDirectory() as directory:
   shell,app=self.fixture(Path(directory))
   try:
    self.assertEqual(os.getpgid(app),shell.pid)
    runner.stop_child_groups([shell])
    self.assertIsNotNone(shell.poll());self.assertTrue(self.alive(app))
   finally:self.cleanup(shell)
 def test_compositor_disconnect_cleans_session_processes(self):
  with tempfile.TemporaryDirectory() as directory:
   shell,app=self.fixture(Path(directory))
   try:
    runner.stop_child_groups([shell],session_disconnected=True)
    end=time.monotonic()+2
    while self.alive(app) and time.monotonic()<end:time.sleep(.01)
    self.assertFalse(self.alive(app))
   finally:self.cleanup(shell)
