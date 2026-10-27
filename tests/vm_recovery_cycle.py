#!/usr/bin/env python3
"""Kill only HICS in the disposable CachyOS guest; preserve a menu-launched Kitty.

Requires a running normal guest session and exactly one Kitty launched through
HICS. Leaves the guest in safe mode for visual inspection and recovery testing.
"""
import argparse, json, subprocess
from pathlib import Path
from vm_cachyos import qmp

REMOTE=r'''
import hashlib,json,os,signal,subprocess,time
from pathlib import Path
assert subprocess.check_output(['systemd-detect-virt'],text=True).strip() in ('kvm','qemu')
assert Path('/etc/hostname').read_text().strip()=='hics-test'
record=Path('/home/hics-test/.local/state/hics/shell-recovery.json')
state=json.loads(record.read_text());assert not state.get('safe') and not state.get('requested'),'Start with a normal guest shell'
app=int(subprocess.check_output(['pgrep','-u','hics-test','-x','kitty'],text=True).strip())
assert Path(f'/proc/{app}/exe').resolve()==Path('/usr/bin/kitty')
report={'appPid':app,'cgroup':Path(f'/proc/{app}/cgroup').read_text(),'crashes':[]}
assert '/app.slice/hics-app-' in report['cgroup'],'Launch Kitty through the actual HICS menu first'
env=dict(os.environ,LANG='ru_RU.UTF-8',XDG_RUNTIME_DIR='/run/user/1000',DBUS_SESSION_BUS_ADDRESS='unix:path=/run/user/1000/bus',WAYLAND_DISPLAY='wayland-1')
def unlocked():
 result=subprocess.check_output(['runuser','-u','hics-test','--','hyprctl','-i','0','-j','locked'],env=env,text=True,timeout=5)
 assert json.loads(result).get('locked') is False,'Authenticate normally before crash testing; never kill the lock owner'
def shell():
 runner=subprocess.check_output(['systemctl','--user','--machine=1000@.host','show','hic-session.service','--property=MainPID','--value'],text=True).strip()
 if runner=='0':return None
 try:children=Path('/proc/'+runner+'/task/'+runner+'/children').read_text().split()
 except FileNotFoundError:return None
 candidates=[]
 for pid in children:
  try:
   if Path('/proc/'+pid+'/comm').read_text().strip()=='hics-qs':candidates.append(int(pid))
  except FileNotFoundError:pass
 assert len(candidates)<=1,{'runner':runner,'mainShellChildren':candidates}
 return candidates[0] if candidates else None
def wait(check):
 end=time.monotonic()+35
 while time.monotonic()<end:
  value=check()
  if value:return value
  time.sleep(.2)
 raise AssertionError('Timed out waiting for guest recovery')
for n in range(2):
 unlocked()
 old=shell();assert old
 executable=Path(f'/proc/{old}/exe');expected=Path('/usr/share/hics/qs/bin/hics-qs')
 assert os.readlink(executable) in (str(expected),str(expected)+' (deleted)'),os.readlink(executable)
 # Package upgrades preserve the old mapped inode until normal restart.
 with executable.open('rb') as active,expected.open('rb') as installed:
  assert hashlib.file_digest(active,'sha256').digest()==hashlib.file_digest(installed,'sha256').digest(),'Mapped shell executable differs; inspect before crash injection'
 os.kill(old,signal.SIGKILL)
 new=wait(lambda: (p if (p:=shell()) and p!=old else None))
 os.kill(app,0);recovery=json.loads(record.read_text())
 report['crashes'].append({'old':old,'new':new,'safe':recovery['safe'],'failures':len(recovery['failures'])})
 assert recovery['safe']==(n==1),recovery
 time.sleep(2)
report['appSurvived']=Path(f'/proc/{app}/cgroup').read_text()==report['cgroup']
assert report['appSurvived']
print(json.dumps(report,indent=2))
'''

def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--lab',type=Path,required=True)
 parser.add_argument('--disposable-cachyos-vm',action='store_true',required=True)
 parser.add_argument('--out',type=Path,required=True)
 args=parser.parse_args();lab=args.lab.resolve()
 if args.out.exists():raise SystemExit('Refusing to replace previous test evidence')
 if not qmp(lab,'query-status').get('running'):raise SystemExit('Guest is not running')
 command=['ssh','-i',str(lab/'guest_ed25519'),'-p','22280','-o','BatchMode=yes','-o','UserKnownHostsFile='+str(lab/'known_hosts-installed'),'root@127.0.0.1','python3','-']
 result=subprocess.run(command,input=REMOTE,text=True,capture_output=True,timeout=100)
 if result.returncode:raise SystemExit(result.stdout+result.stderr)
 report=json.loads(result.stdout);args.out.write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps(report,indent=2))
if __name__=='__main__':main()
