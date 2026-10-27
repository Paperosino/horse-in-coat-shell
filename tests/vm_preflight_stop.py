#!/usr/bin/env python3
"""Real user-systemd stop of installed runner with isolated preflight stalls.

The compositor event endpoint and helper delay are fixtures. Main session and
its lock owner are never stopped. Only a hics-test KVM/QEMU guest is accepted.
"""
import argparse,json,subprocess
from pathlib import Path
REMOTE=r"""
import json,os,signal,socket,subprocess,tempfile,time,uuid
from pathlib import Path
assert Path('/etc/hostname').read_text().strip()=='hics-test'
assert subprocess.check_output(['systemd-detect-virt'],text=True).strip() in ('kvm','qemu')
assert os.getuid()==1000
bus=dict(os.environ,XDG_RUNTIME_DIR='/run/user/1000',DBUS_SESSION_BUS_ADDRESS='unix:path=/run/user/1000/bus',LANG='ru_RU.UTF-8')
def control(*args):return subprocess.check_output(['systemctl','--user',*args],env=bus,text=True,timeout=15).strip()
main_before=control('show','hic-session.service','-p','MainPID','--value')
app_before=subprocess.check_output(['pgrep','-x','kitty'],text=True).strip()
unit='hics-preflight-lab-'+uuid.uuid4().hex+'.service'
handles=[]
with tempfile.TemporaryDirectory(prefix='hics-preflight-stop-',dir='/var/tmp') as directory:
 base=Path(directory);runtime=base/'runtime';endpoint=runtime/'hypr/stop-fixture/.socket2.sock';endpoint.parent.mkdir(parents=True)
 server=socket.socket(socket.AF_UNIX);server.bind(str(endpoint));server.listen(2)
 hook=base/'hooks';hook.mkdir()
 (hook/'sitecustomize.py').write_text('''import os,sys,time,subprocess,json,types
from pathlib import Path
base=Path(os.environ['HICS_LAB_ROOT'])
name=Path(sys.argv[0]).name
if name in ('accessibility_manager.py','display_profiles.py','configuration_manager.py'):
 child=subprocess.Popen(['sleep','60'])
 (base/(name+'.json')).write_text(json.dumps({'pid':os.getpid(),'child':child.pid}))
 time.sleep(60)
if name=='session_runner.py':
 sys.modules['appearance_themes']=types.SimpleNamespace(STATE=base/'absent',session_environment=lambda:{})
 sys.modules['gtk_theme']=types.SimpleNamespace(restore=lambda:None)
''')
 try:
  command=['systemd-run','--user','--unit='+unit,'--property=KillMode=process','--property=TimeoutStopSec=10','--property=Restart=no',
   '--setenv=PYTHONPATH='+str(hook),'--setenv=HICS_LAB_ROOT='+str(base),
   '--setenv=XDG_RUNTIME_DIR='+str(runtime),'--setenv=HYPRLAND_INSTANCE_SIGNATURE=stop-fixture',
   '--setenv=XDG_CONFIG_HOME='+str(base/'config'),'--setenv=XDG_STATE_HOME='+str(base/'state'),
   '--setenv=XDG_DATA_HOME='+str(base/'data'),'--setenv=HICS_SAFE_MODE=0',
   '/usr/bin/python3','/usr/share/hics/shell/assets/session_runner.py','run']
  subprocess.run(command,env=bus,check=True,capture_output=True,text=True,timeout=10)
  deadline=time.monotonic()+8
  markers=[]
  while time.monotonic()<deadline:
   markers=list(base.glob('*.py.json'))
   if len(markers)==3:break
   time.sleep(.05)
  assert len(markers)==3,'Not all delayed preflight helpers started'
  processes=[json.loads(p.read_text()) for p in markers]
  for process in processes:
   for pid in process.values():handles.append(os.pidfd_open(pid))
  started=time.monotonic();control('stop',unit);elapsed=time.monotonic()-started
  details=control('show',unit,'-p','Result','-p','ExecMainStatus','-p','NRestarts')
  assert 'Result=success' in details and 'ExecMainStatus=0' in details,details
  assert elapsed<8,elapsed
  def active(pid):
   try:return Path(f'/proc/{pid}/stat').read_text().rsplit(')',1)[1].split()[0]!='Z'
   except (FileNotFoundError,ProcessLookupError):return False
  deadline=time.monotonic()+2
  while any(active(pid) for item in processes for pid in item.values()) and time.monotonic()<deadline:time.sleep(.02)
  assert not any(active(pid) for item in processes for pid in item.values()),processes
  record=json.loads((base/'state/hics/shell-recovery.json').read_text())
  assert record['active'] is False and not record['failures'],record
  assert control('show','hic-session.service','-p','MainPID','--value')==main_before
  assert subprocess.check_output(['pgrep','-x','kitty'],text=True).strip()==app_before
  print(json.dumps({'unit':unit,'stopSeconds':elapsed,'details':details,'helpers':processes,'record':record,'mainRunnerPreserved':main_before,'appPreserved':app_before,'version':subprocess.check_output(['pacman','-Q','hic-shell'],text=True).strip()},indent=2))
 finally:
  subprocess.run(['systemctl','--user','stop',unit],env=bus,capture_output=True,timeout=15)
  for fd in handles:
   try:signal.pidfd_send_signal(fd,signal.SIGKILL)
   except ProcessLookupError:pass
   finally:os.close(fd)
  server.close()
"""
p=argparse.ArgumentParser();p.add_argument('--lab',required=True,type=Path);p.add_argument('--output',required=True,type=Path);a=p.parse_args()
cmd=['ssh','-i',str(a.lab/'guest_ed25519'),'-p','22280','-o','BatchMode=yes','-o','ConnectTimeout=5','-o','UserKnownHostsFile='+str(a.lab/'known_hosts-installed'),'root@127.0.0.1','runuser -u hics-test -- python3 -']
r=subprocess.run(cmd,input=REMOTE,text=True,capture_output=True,timeout=50)
if r.returncode:raise SystemExit(r.stdout+r.stderr)
report=json.loads(r.stdout);a.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
