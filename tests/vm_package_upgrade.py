#!/usr/bin/env python3
"""Upgrade the disposable CachyOS guest while its real session is locked.

Does not unlock or kill the session. Requires a package already copied into
/var/tmp and the lab-only ordinary-user pacman sudo rule.
"""
import argparse, json, shlex, subprocess
from pathlib import Path
REMOTE=r'''
import hashlib,json,os,subprocess,sys,time
from pathlib import Path
assert Path('/etc/hostname').read_text().strip()=='hics-test'
assert subprocess.check_output(['systemd-detect-virt'],text=True).strip() in ('kvm','qemu')
session_mode=sys.argv[2];assert session_mode in ('locked','safe')
package=Path(sys.argv[1]);assert package.is_file() and package.parent==Path('/var/tmp') and package.name.startswith('hic-shell-') and package.name.endswith('.pkg.tar.zst')
package.chmod(0o644)
env=dict(os.environ,LANG='ru_RU.UTF-8',XDG_RUNTIME_DIR='/run/user/1000',DBUS_SESSION_BUS_ADDRESS='unix:path=/run/user/1000/bus',WAYLAND_DISPLAY='wayland-1')
def user(*args):return subprocess.check_output(['runuser','-u','hics-test','--',*args],env=env,text=True,timeout=10).strip()
def state():
 runner=int(subprocess.check_output(['systemctl','--user','--machine=1000@.host','show','hic-session.service','--property=MainPID','--value'],text=True).strip())
 children=Path('/proc/'+str(runner)+'/task/'+str(runner)+'/children').read_text().split()
 shells=[]
 for pid in children:
  try:
   if Path('/proc/'+pid+'/comm').read_text().strip()=='hics-qs':shells.append(pid)
  except FileNotFoundError:pass
 assert len(shells)==1,{'runner':runner,'mainShellChildren':shells}
 return {'runner':runner,'shell':shells[0],'apps':user('pgrep','-x','kitty'),
 'locked':'true' if json.loads(user('hyprctl','-i','0','-j','locked'))['locked'] else 'false',
 'binds':len(json.loads(user('hyprctl','-i','0','-j','binds'))),
 'errors':user('hyprctl','-i','0','configerrors')}

before=state();assert before['locked']==('true' if session_mode=='locked' else 'false') and before['binds']>10 and not before['errors'],before
if session_mode=='safe':assert json.loads(Path('/home/hics-test/.local/state/hics/shell-recovery.json').read_text()).get('safe') is True
assert not Path('/var/lib/pacman/db.lck').exists(),'Another package transaction is active'
log=Path('/var/tmp/hics-package-upgrade.log')
with log.open('w') as stream:
 process=subprocess.Popen(['systemd-inhibit','--what=idle:sleep','--mode=block','--who=hics-tests','--why=locked-package-test','runuser','-u','hics-test','--','/var/tmp/install.sh','--package',str(package)],stdin=subprocess.PIPE,stdout=stream,stderr=subprocess.STDOUT)
 try:
  process.communicate(input=b'\n'*20,timeout=240)
 except BaseException:
  # Do not kill pacman/the lock owner on an observation failure.
  print(json.dumps({'installerPid':process.pid,'log':str(log),'before':before}));raise
assert process.returncode==0,log.read_text()[-6000:]
for _ in range(80):
 option=json.loads(user('hyprctl','-i','0','-j','getoption','misc:disable_autoreload'))
 if not option['bool']:break
 time.sleep(.1)
else:raise AssertionError('Package guard did not restore autoreload')
after=state();assert after==before,{'before':before,'after':after}
assert not Path('/var/lib/pacman/db.lck').exists()
unit=subprocess.run(['systemctl','--user','--machine=1000@.host','is-active','--quiet','hics-package-config-guard.service'],timeout=5)
assert unit.returncode!=0,'A package guard was left running'
with package.open('rb') as stream: package_sha256=hashlib.file_digest(stream,'sha256').hexdigest()
print(json.dumps({'sessionMode':session_mode,'packageSha256':package_sha256,'before':before,'after':after,'version':subprocess.check_output(['pacman','-Q','hic-shell'],text=True).strip(),'autoreloadRestored':True,'log':str(log)},indent=2))
'''
p=argparse.ArgumentParser();p.add_argument('--lab',required=True,type=Path);p.add_argument('--package',required=True);p.add_argument('--output',required=True,type=Path);p.add_argument('--session-mode',choices=['locked','safe'],default='locked');p.add_argument('--ssh-port',type=int,default=22280);p.add_argument('--identity',type=Path);p.add_argument('--known-hosts',type=Path);a=p.parse_args()
command=['ssh','-i',str(a.identity or a.lab/'guest_ed25519'),'-p',str(a.ssh_port),'-o','BatchMode=yes','-o','ConnectTimeout=5','-o','UserKnownHostsFile='+str(a.known_hosts or a.lab/'known_hosts-installed'),'root@127.0.0.1','python3 - '+shlex.quote(a.package)+' '+shlex.quote(a.session_mode)]
result=subprocess.run(command,input=REMOTE,capture_output=True,text=True,timeout=280)
if result.returncode:raise SystemExit(result.stdout+result.stderr)
report=json.loads(result.stdout);a.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
