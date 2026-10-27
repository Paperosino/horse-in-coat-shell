#!/usr/bin/env python3
"""Test coordinated transitions in the disposable guest; never unlocks PAM."""
import argparse,json,shlex,subprocess
from pathlib import Path
REMOTE=r'''
import json,os,subprocess,sys,time
from pathlib import Path
assert Path('/etc/hostname').read_text().strip()=='hics-test'
assert subprocess.check_output(['systemd-detect-virt'],text=True).strip() in ('kvm','qemu')
phase=sys.argv[1];assert phase in ('locked','unlocked')
env=dict(os.environ,LANG='ru_RU.UTF-8',XDG_RUNTIME_DIR='/run/user/1000',WAYLAND_DISPLAY='wayland-1',DBUS_SESSION_BUS_ADDRESS='unix:path=/run/user/1000/bus')
def user(*args):return subprocess.run(['runuser','-u','hics-test','--',*args],env=env,text=True,capture_output=True,timeout=12)
def ctl(*args):
 p=user('hyprctl','-i','0',*args);assert p.returncode==0,p.stderr;return p.stdout.strip()
record=Path('/home/hics-test/.local/state/hics/shell-recovery.json')
def state():
 runner=int(subprocess.check_output(['systemctl','--user','--machine=1000@.host','show','hic-session.service','-p','MainPID','--value'],text=True))
 children=Path(f'/proc/{runner}/task/{runner}/children').read_text().split()
 shells=[]
 for pid in children:
  try:
   if Path('/proc/'+pid+'/comm').read_text().strip()=='hics-qs':shells.append(int(pid))
  except FileNotFoundError:pass
 assert len(shells)==1,shells
 return {'runner':runner,'shell':shells[0],'locked':json.loads(ctl('-j','locked'))['locked'],'record':json.loads(record.read_text()),'errors':ctl('configerrors'),'apps':user('pgrep','-x','kitty').stdout.strip(),'binds':len(json.loads(ctl('-j','binds')))}
def helper(action):return user('python3','/usr/share/hics/shell/assets/shell_recovery.py',action)
def wait_mode(safe,previous):
 end=time.monotonic()+45;last=None
 while time.monotonic()<end:
  try:
   last=state()
   if last['shell']!=previous['shell'] and last['record'].get('safe')==safe:
    assert last['runner']==previous['runner'],last
    assert last['apps']==previous['apps'] and not last['errors'] and not last['locked'],last
    assert last['record'].get('failures')==[],last
    return last
  except (AssertionError,FileNotFoundError):pass
  time.sleep(.15)
 raise AssertionError({'timeout':last})
before=state();report={'phase':phase,'before':before,'steps':[]}
assert before['apps'] and not before['errors'],before
if phase=='locked':
 if not before['locked']:
  r=user('/usr/share/hics/qs/bin/hics-qs','ipc','-p','/usr/share/hics/shell','call','lock','lock');assert r.returncode==0,r.stderr
  for _ in range(80):
   if json.loads(ctl('-j','locked'))['locked']:break
   time.sleep(.1)
 before=state();assert before['locked'];report['before']=before
 saved=record.read_bytes()
 for action in ('on','resume'):
  r=helper(action);assert r.returncode!=0,(r.stdout,r.stderr)
  assert 'Unlock' in r.stdout,(r.stdout,r.stderr)
  after=state();assert after==before and record.read_bytes()==saved,after
  report['steps'].append({'action':action,'rejected':True,'after':after})
else:
 for _ in range(50):
  if not before['locked']:break
  time.sleep(.1);before=state()
 assert not before['locked'],'Authenticate normally with PAM before this phase'
 current=before
 for action,safe in [('on',True),('resume',False)]*3:
  r=helper(action);assert r.returncode==0,(r.stdout,r.stderr)
  current=wait_mode(safe,current)
  report['steps'].append({'action':action,'after':current})
report['version']=subprocess.check_output(['pacman','-Q','hic-shell'],text=True).strip()
print(json.dumps(report,indent=2))
'''
p=argparse.ArgumentParser();p.add_argument('--lab',type=Path,required=True);p.add_argument('--phase',choices=['locked','unlocked'],required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
cmd=['ssh','-i',str(a.lab/'guest_ed25519'),'-p','22280','-o','BatchMode=yes','-o','ConnectTimeout=5','-o','UserKnownHostsFile='+str(a.lab/'known_hosts-installed'),'root@127.0.0.1','python3 - '+shlex.quote(a.phase)]
r=subprocess.run(cmd,input=REMOTE,text=True,capture_output=True,timeout=300)
if r.returncode:raise SystemExit(r.stdout+r.stderr)
data=json.loads(r.stdout);a.output.write_text(json.dumps(data,indent=2)+'\n');print(json.dumps(data,indent=2))
