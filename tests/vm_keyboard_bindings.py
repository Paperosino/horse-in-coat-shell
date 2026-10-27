#!/usr/bin/env python3
"""Use the intentional recovery retry in unlocked VM; check keybind lifetimes.

Requires normal PAM unlock beforehand. Does not unlock a session, remove binds
by key, unload plugins, or terminate the independent test application.
"""
import argparse,json,shlex,subprocess
from pathlib import Path
REMOTE=r'''
import json,os,subprocess,time
from pathlib import Path
assert Path('/etc/hostname').read_text().strip()=='hics-test'
assert subprocess.check_output(['systemd-detect-virt'],text=True).strip() in ('kvm','qemu')
assert 'hics_keyboard_state_bindings' in Path('/usr/share/hics/shell/services/KeyboardStateBindings.js').read_text()
env=dict(os.environ,LANG='ru_RU.UTF-8',XDG_RUNTIME_DIR='/run/user/1000',DBUS_SESSION_BUS_ADDRESS='unix:path=/run/user/1000/bus',WAYLAND_DISPLAY='wayland-1')
def user(*args):return subprocess.check_output(['runuser','-u','hics-test','--',*args],env=env,text=True,timeout=5).strip()
def ctl(*args):return user('hyprctl','-i','0',*args)
def locked():return user('/usr/share/hics/qs/bin/hics-qs','ipc','-p','/usr/share/hics/shell','call','lock','isLocked')
def shell():
 runner=user('systemctl','--user','show','hic-session.service','--property=MainPID','--value')
 if runner=='0':raise ProcessLookupError('Session runner is not ready')
 try:children=Path('/proc/'+runner+'/task/'+runner+'/children').read_text().split()
 except FileNotFoundError:raise ProcessLookupError('Session runner exited')
 candidates=[]
 for value in children:
  try:
   if Path('/proc/'+value+'/comm').read_text().strip()=='hics-qs':candidates.append(value)
  except FileNotFoundError:pass
 if not candidates:raise ProcessLookupError('No direct main shell child yet')
 assert len(candidates)==1,{'runner':runner,'mainShellChildren':candidates}
 return candidates[0]

def binds():return json.loads(ctl('-j','binds'))
def ours(row):return row.get('description') in ('Custom: Caps_Lock','Custom: Num_Lock') and row.get('dispatcher')=='__lua'
def others(rows):
 result=[]
 for row in rows:
  if ours(row):continue
  item=dict(row)
  if item.get('dispatcher')=='__lua':item.pop('arg',None) # IDs are opaque and change on reload; never replay them.
  result.append(json.dumps(item,sort_keys=True))
 return sorted(result)
assert locked()=='false','Authenticate normally; never restart the lock owner'
recovery=json.loads(Path('/home/hics-test/.local/state/hics/shell-recovery.json').read_text())
assert not recovery.get('safe') and not recovery.get('requested')
application=user('pgrep','-x','kitty');cgroup=Path('/proc/'+application+'/cgroup').read_text();assert '/app.slice/hics-app-' in cgroup
before=binds();baseline=others(before)
limits=subprocess.check_output(['systemctl','--user','--machine=1000@.host','show','hic-session.service','-p','StartLimitBurst','-p','StartLimitIntervalUSec'],text=True).strip()
report={'startLimitPolicy':limits,'restartMethod':'explicit shell_recovery resume (resets failed counter, not unit policy)','package':subprocess.check_output(['pacman','-Q','hic-shell'],text=True).strip(),'before':{'total':len(before),'owned':sum(ours(x) for x in before)},'stages':[],'application':application}
record=Path('/var/tmp/hics-keyboard-cycle.json')
def preserve(stage):
 rows=binds();owned=[x for x in rows if ours(x)]
 assert len(owned)==2,{'stage':stage,'owned':len(owned)}
 assert {x['key'] for x in owned}=={'Caps_Lock','Num_Lock'}
 assert all(x['locked'] and x['release'] and x['non_consuming'] for x in owned)
 assert others(rows)==baseline,'Other binding metadata changed'
 assert user('pgrep','-x','kitty')==application and Path('/proc/'+application+'/cgroup').read_text()==cgroup
 assert not ctl('configerrors'),ctl('configerrors')
 report['stages'].append({'stage':stage,'pid':shell(),'total':len(rows),'owned':len(owned),'applicationSurvived':True})
 record.write_text(json.dumps(report,indent=2))
def restart():
 assert locked()=='false','No restart attempted while locked'
 old=shell()
 result=json.loads(user('python3','/usr/share/hics/shell/assets/shell_recovery.py','resume'))
 assert result.get('restarting'),result
 for _ in range(100):
  try:
   current=shell()
   if current!=old and locked()=='false':return
  except (subprocess.CalledProcessError,ProcessLookupError):pass
  time.sleep(.2)
 raise AssertionError('New normal shell did not become ready')
def reload():
 ctl('reload')
 for _ in range(100):
  if sum(ours(x) for x in binds())==2:return
  time.sleep(.1)
 raise AssertionError('Keyboard state bindings did not recover after config reload')
restart();reload();preserve('old-duplicates-cleared-by-config-reload')
for index in range(3):
 restart();preserve('shell-restart-'+str(index+1))
 reload();preserve('config-reload-'+str(index+1))
print(json.dumps(report,indent=2))
'''
p=argparse.ArgumentParser();p.add_argument('--lab',required=True,type=Path);p.add_argument('--out',required=True,type=Path);p.add_argument('--disposable-cachyos-vm',required=True,action='store_true');a=p.parse_args()
if a.out.exists():raise SystemExit('Choose a fresh output file')
command=['ssh','-i',str(a.lab/'guest_ed25519'),'-p','22280','-o','BatchMode=yes','-o','ConnectTimeout=5','-o','UserKnownHostsFile='+str(a.lab/'known_hosts-installed'),'root@127.0.0.1','systemd-inhibit --what=idle:sleep --mode=block --who=hics-tests --why=keyboard-lifecycle python3 -']
r=subprocess.run(command,input=REMOTE,text=True,capture_output=True,timeout=180)
if r.returncode:raise SystemExit(r.stdout+r.stderr)
report=json.loads(r.stdout);a.out.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
