#!/usr/bin/env python3
"""Real recovery QML under ENOSPC/EROFS; explicit disposable guest only.

Uses private XDG directories and a fixture compositor-event endpoint. The
installed guest compositor only renders the recovery window; its lock owner
and applications are never restarted. This is not a full login test.
"""
import argparse, hashlib, json, subprocess, tarfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
WORKER=r'''
import errno,hashlib,json,os,signal,socket,subprocess,sys,time
from pathlib import Path
assert os.getuid()==1000
root=Path(sys.argv[1]);mode=sys.argv[2]
runtime=root/'runtime';runtime.mkdir(mode=0o700)
wayland=Path('/run/user/1000/wayland-1');assert wayland.exists()
(runtime/'wayland-1').symlink_to(wayland)
endpoint=runtime/'hypr/storage-fixture/.socket2.sock';endpoint.parent.mkdir(parents=True)
server=socket.socket(socket.AF_UNIX);server.bind(str(endpoint));server.listen(16)
bus=dict(os.environ,XDG_RUNTIME_DIR='/run/user/1000',DBUS_SESSION_BUS_ADDRESS='unix:path=/run/user/1000/bus')
def main_pid():return subprocess.check_output(['systemctl','--user','show','hic-session.service','-p','MainPID','--value'],env=bus,text=True).strip()
before=main_pid()
apps=subprocess.check_output(['pgrep','-x','kitty'],text=True).strip()
if mode=='full':
 written=0
 with (root/'state/fill').open('wb',buffering=0) as stream:
  while True:
   try:written+=stream.write(b'x'*65536)
   except OSError as error:assert error.errno==errno.ENOSPC;break
 assert written<=2*1024*1024
else:written=0
# The fixture bus cannot activate real user services.
env=dict(os.environ,HOME=str(root/'home'),XDG_RUNTIME_DIR=str(runtime),XDG_CONFIG_HOME=str(root/'config'),XDG_STATE_HOME=str(root/'state'),XDG_DATA_HOME=str(root/'data'),XDG_CACHE_HOME=str(root/'cache'),WAYLAND_DISPLAY='wayland-1',HYPRLAND_INSTANCE_SIGNATURE='storage-fixture',HICS_DATA_DIR=str(root/'payload'),HICS_SAFE_MODE='0',PATH=str(root/'bin')+':'+os.environ['PATH'],PYTHONDONTWRITEBYTECODE='1',DBUS_SESSION_BUS_ADDRESS='unix:path='+str(root/'absent-session'),DBUS_SYSTEM_BUS_ADDRESS='unix:path='+str(root/'absent-system'),LANG='ru_RU.UTF-8')
for key in ('HICS_SHELL_DIR','HYPRSTACK_SHELL_DIR','FONTCONFIG_FILE'):env.pop(key,None)
with (root/'runner.log').open('w') as log:
 runner=subprocess.Popen(['python3',str(root/'payload/shell/assets/session_runner.py'),'run'],env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
 child=None
 try:
  transitions=[]
  for action in (None,'on','resume'):
   previous_child=child
   if action:
    reply=subprocess.run([str(root/'payload/qs/bin/hics-qs'),'ipc','-p',str(root/'payload/shell/recovery'),'call','sessionControl','transition',action],env=env,capture_output=True,text=True,timeout=5)
    assert reply.returncode==0 and reply.stdout.strip()=='true',reply.stdout+reply.stderr
   child=None
   deadline=time.monotonic()+20
   mapped=None
   while time.monotonic()<deadline:
    assert runner.poll() is None,(root/'runner.log').read_text()
    children=Path(f'/proc/{runner.pid}/task/{runner.pid}/children').read_text().split()
    for pid in children:
     try:
      if Path('/proc/'+pid+'/comm').read_text().strip()=='hics-qs':child=int(pid) if int(pid)!=previous_child else None
     except FileNotFoundError:pass
    clients=json.loads(subprocess.check_output(['hyprctl','-i','0','clients','-j'],env=bus,text=True))
    mapped=next((c for c in clients if c.get('pid')==child and 'Безопасный режим' in c.get('title','')),None)
    if mapped and mapped.get('mapped') and all(v>100 for v in mapped['size']):break
    time.sleep(.1)
   assert mapped and mapped.get('mapped'),(root/'runner.log').read_text()
   assert child is not None
   actual=Path(f'/proc/{child}/environ').read_bytes().split(b'\0')
   assert b'HICS_SAFE_MODE=1' in actual
   transitions.append({'request':action or 'startup','child':child,'safe':True})
   if previous_child:assert not Path(f'/proc/{previous_child}').exists()
  # Keep the real scene and helper alive long enough to detect early QML failures.
  time.sleep(2);assert runner.poll() is None and Path(f'/proc/{child}').exists()
  output=(root/'runner.log').read_text()
  assert 'using recovery' in output,output
  assert 'TypeError' not in output and 'failed to load configuration' not in output.lower(),output
  runner.send_signal(signal.SIGTERM);runner.wait(timeout=10);assert runner.returncode==0,output
  assert not Path(f'/proc/{child}').exists(),'Recovery child leaked'
  assert main_pid()==before
  assert subprocess.check_output(['pgrep','-x','kitty'],text=True).strip()==apps
  print(json.dumps({'mode':mode,'filledBytes':written,'mappedTitle':mapped['title'],'size':mapped['size'],'runnerExit':runner.returncode,'mainRunnerPreserved':before,'appsPreserved':apps,'safeModeEnvironment':True,'runnerSha256':hashlib.sha256((root/'payload/shell/assets/session_runner.py').read_bytes()).hexdigest(),'transitions':transitions,'log':output}))
 finally:
  if runner.poll() is None:
   runner.terminate()
   try:runner.wait(timeout=10)
   except subprocess.TimeoutExpired:runner.kill();runner.wait()
  server.close()
'''
REMOTE=r'''
import json,os,shutil,subprocess,sys,tarfile,tempfile
from pathlib import Path
assert os.geteuid()==0
assert Path('/etc/hostname').read_text().strip()=='hics-test'
assert subprocess.check_output(['systemd-detect-virt'],text=True).strip() in ('qemu','kvm')
reports=[]
for mode in ('full','readonly'):
 root=Path(tempfile.mkdtemp(prefix='hics-recovery-storage-',dir='/var/tmp'));root.chmod(0o755)
 mounted=False;preserve=False
 try:
  with tarfile.open('/var/tmp/hics-recovery-storage.tar.gz') as archive:archive.extractall(root,filter='data')
  if USE_INSTALLED:
   for name in ('assets','recovery'):
    path=root/'payload/shell'/name;shutil.rmtree(path);path.symlink_to('/usr/share/hics/shell/'+name,target_is_directory=True)
   shutil.copy2('/usr/bin/hics-shell',root/'bin/hics-shell')
  (root/'payload/qs').symlink_to('/usr/share/hics/qs',target_is_directory=True)
  (root/'payload/qml').symlink_to('/usr/share/hics/qml',target_is_directory=True)
  for name in ('home','state','config','data','cache'):(root/name).mkdir(mode=0o700)
  for path in (root,*root.rglob('*')):
   if not path.is_symlink():os.chown(path,1000,1000)
  (root/'bin/hics-shell').chmod(0o755)
  subprocess.run(['mount','-t','tmpfs','-o','size=2M,mode=0700,uid=1000,gid=1000','hics-recovery-lab',str(root/'state')],check=True);mounted=True
  if mode=='readonly':subprocess.run(['mount','-o','remount,ro',str(root/'state')],check=True)
  worker=root/'worker.py';worker.write_text(WORKER);worker.chmod(0o644)
  process=subprocess.Popen(['runuser','-u','hics-test','--','python3',str(worker),str(root),mode],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,start_new_session=True)
  try:stdout,stderr=process.communicate(timeout=45)
  except subprocess.TimeoutExpired:
   preserve=True
   raise RuntimeError('Observation timed out; inspect live worker '+str(process.pid)+' at '+str(root)+' before cleanup')
  assert process.returncode==0,stdout+stderr
  reports.append(json.loads(stdout))
 finally:
  if not preserve:
   if mounted:subprocess.run(['umount',str(root/'state')],check=True)
   shutil.rmtree(root)
print(json.dumps({'cases':reports,'package':subprocess.check_output(['pacman','-Q','hic-shell'],text=True).strip()}))
'''
p=argparse.ArgumentParser();p.add_argument('--lab',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--disposable-cachyos-vm',action='store_true',required=True);p.add_argument('--installed',action='store_true');a=p.parse_args()
if a.output.exists():raise SystemExit('Use a fresh evidence path')
archive=a.lab/(a.output.stem+'-sources.tar.gz')
with tarfile.open(archive,'w:gz') as bundle:
 for path in sorted((ROOT/'shell/assets').glob('*.py')):bundle.add(path,arcname='payload/shell/assets/'+path.name)
 bundle.add(ROOT/'shell/assets/feature_data',arcname='payload/shell/assets/feature_data')
 bundle.add(ROOT/'shell/recovery',arcname='payload/shell/recovery')
 bundle.add(ROOT/'distribution/bin/hics-shell',arcname='bin/hics-shell')
key=['-i',str(a.lab/'guest_ed25519'),'-o','BatchMode=yes','-o','ConnectTimeout=5','-o','UserKnownHostsFile='+str(a.lab/'known_hosts-installed')]
subprocess.run(['scp',*key,'-P','22280',str(archive),'root@127.0.0.1:/var/tmp/hics-recovery-storage.tar.gz'],check=True)
result=subprocess.run(['ssh',*key,'-p','22280','root@127.0.0.1','python3 -'],input='WORKER='+repr(WORKER)+'\nUSE_INSTALLED='+repr(a.installed)+'\n'+REMOTE,capture_output=True,text=True,timeout=110)
if result.returncode:raise SystemExit(result.stdout+result.stderr)
report=json.loads(result.stdout);assert all(case['runnerSha256']==hashlib.sha256((ROOT/'shell/assets/session_runner.py').read_bytes()).hexdigest() for case in report['cases']);report['sourceMode']='installed' if a.installed else 'snapshot';report['archiveSha256']=hashlib.sha256(archive.read_bytes()).hexdigest();report['runnerSha256']=hashlib.sha256((ROOT/'shell/assets/session_runner.py').read_bytes()).hexdigest();a.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
