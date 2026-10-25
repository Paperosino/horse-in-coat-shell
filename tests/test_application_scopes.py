"""Real user-systemd isolation test, using only disposable fixture processes."""
import json,os,shlex,subprocess,tempfile,time,unittest,uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
@unittest.skipUnless(Path(os.environ.get('XDG_RUNTIME_DIR','/nonexistent')+'/systemd/private').exists(),'requires a running user systemd manager')
class ApplicationScopes(unittest.TestCase):
 def test_gio_startup_failure_reaches_the_original_launcher(self):
  with tempfile.TemporaryDirectory(prefix='hics-launch-feedback-') as temporary:
   base=Path(temporary)
   flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','Qt6Core'],text=True))
   subprocess.run(['c++','-std=c++20','-fPIC',str(ROOT/'tests/fixtures/application-launch-probe.cpp'),'-I',str(ROOT/'shell/plugin/include'),*flags,'-o',str(base/'probe')],check=True,capture_output=True)
   desktop=base/'broken.desktop';desktop.write_text('[Desktop Entry]\nType=Application\nName=Broken fixture\nExec=/hics-fixture-does-not-exist\n')
   env=dict(os.environ,PATH=str(ROOT/'build/native/app-launch')+':'+os.environ['PATH'])
   result=subprocess.run([str(base/'probe'),str(desktop),str(base/'launch.log')],env=env,capture_output=True,text=True,timeout=15)
   self.assertEqual(result.returncode,0,result.stdout+result.stderr)
   feedback=json.loads(result.stdout);self.assertNotEqual(feedback['code'],0)
   self.assertTrue(feedback['error'].strip(),feedback)
 def test_survives_launcher_service_crash_without_inheriting_hardening(self):
  ident=uuid.uuid4().hex;origin='hics-test-origin-'+ident+'.service';scope=None
  with tempfile.TemporaryDirectory(prefix='hics-scope-test-') as temporary:
   base=Path(temporary);trace=base/'trace.json'
   child=base/'child.py';child.write_text('import json,os,sys,time\nfrom pathlib import Path\nPath(sys.argv[1]).write_text(json.dumps({"pid":os.getpid(),"args":sys.argv[2:],"environment":os.getenv("HICS_SCOPE_ENV")}))\ntime.sleep(45)\n')
   parent=base/'parent.py';parent.write_text('import subprocess,sys,time\nsubprocess.run(sys.argv[1:],check=True)\ntime.sleep(45)\n')
   try:
    subprocess.run(['systemd-run','--user','--quiet','--collect','--unit='+origin,'--expand-environment=no','--property=NoNewPrivileges=yes','--setenv=HICS_SCOPE_ENV=custom value $HOME \"quoted\"','--','/usr/bin/python3',str(parent),str(ROOT/'build/native/app-launch/hics-launch'),'--','/usr/bin/python3',str(child),str(trace),'space in argument','Привет','$(not-a-shell)','$HOME','%u','100%'],check=True,capture_output=True,text=True)
    for _ in range(100):
     if trace.exists():break
     time.sleep(.05)
    self.assertTrue(trace.exists(),'application failed to reach its scope')
    data=json.loads(trace.read_text());pid=data['pid'];group=Path(f'/proc/{pid}/cgroup').read_text();scope=group.strip().split('/')[-1]
    self.assertIn('/app.slice/hics-app-',group);self.assertTrue(scope.endswith('.scope'))
    self.assertIn('NoNewPrivs:\t0',Path(f'/proc/{pid}/status').read_text())
    self.assertEqual(data['environment'],'custom value $HOME \"quoted\"')
    self.assertEqual(data['args'],['space in argument','Привет','$(not-a-shell)','$HOME','%u','100%'])
    subprocess.run(['systemctl','--user','kill','--kill-whom=all','--signal=SIGKILL',origin],check=True,capture_output=True)
    time.sleep(.15);os.kill(pid,0)
    # systemd-run --scope execs the workload: the scope contains no resident
    # shell, Python bootstrap, launcher helper or extra systemd-run process.
    contents=Path('/sys/fs/cgroup'+group.strip().split(':',2)[2]+'/cgroup.procs').read_text().split()
    self.assertEqual(contents,[str(pid)])
   finally:
    subprocess.run(['systemctl','--user','stop',origin],capture_output=True)
    if scope:subprocess.run(['systemctl','--user','stop',scope],capture_output=True)
if __name__=='__main__':unittest.main()
