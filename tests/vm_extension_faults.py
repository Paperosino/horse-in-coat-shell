#!/usr/bin/env python3
"""Installed helpers in disposable CachyOS; temporary XDG homes, no session restart."""
import argparse,json,subprocess
from pathlib import Path
REMOTE=r'''
import hashlib,json,os,subprocess,sys,tempfile
from pathlib import Path
assert os.getuid()==1000 and Path('/etc/hostname').read_text().strip()=='hics-test'
assert subprocess.check_output(['systemd-detect-virt'],text=True).strip() in ('kvm','qemu')
with tempfile.TemporaryDirectory(prefix='hics-installed-extension-faults-') as temporary:
 root=Path(temporary)
 for key in ('CONFIG','DATA','STATE','CACHE'):os.environ['XDG_'+key+'_HOME']=str(root/key.lower())
 sys.path.insert(0,'/usr/share/hics/shell/assets')
 import plugin_manager as m,extension_recovery as r,shell_recovery as recovery
 source=root/'source';source.mkdir();(source/'manifest.json').write_text('{"api":"hics-1","id":"vm-fixture","entryPoints":{}}')
 m.install(str(source));m.enable('vm-fixture',True)
 assert m.find('vm-fixture')['enabled']
 before=(m.USER/'vm-fixture/manifest.json').read_bytes()
 outcomes=[]
 for label,raw in [('invalid-json',b'{invalid'),('wrong-schema',b'{"enabled":[]}'),('deep-json',b'{"deep":'+b'['*2000+b'0'+b']'*2000+b'}')]:
  m.PREFS.write_bytes(raw)
  state=m.scan();assert state['recoveryMode'] and state['errors'] and not any(p['enabled'] for p in state['plugins'])
  result=subprocess.run([sys.executable,'/usr/share/hics/shell/assets/plugin_manager.py','recovery','off'],capture_output=True,text=True,timeout=5)
  assert result.returncode==1 and 'file was preserved' in json.loads(result.stdout)['error']
  assert m.PREFS.read_bytes()==raw
  outcomes.append(label)
 m.PREFS.unlink();os.mkfifo(m.PREFS)
 assert m.scan()['recoveryMode'];m.PREFS.unlink();outcomes.append('fifo')
 outside=root/'outside';outside.write_text('{"enabled":{"vm-fixture":true}}');m.PREFS.symlink_to(outside)
 assert m.scan()['recoveryMode'] and m.PREFS.is_symlink()
 assert outside.read_text()=='{"enabled":{"vm-fixture":true}}';m.PREFS.unlink();outcomes.append('symlink')
 r.MARKER.parent.mkdir(parents=True,exist_ok=True);os.mkfifo(r.MARKER);r.begin();assert r.MARKER.is_file() and m.scan()['recoveryMode'];outcomes.append('marker-fifo')
 m.PREFS.write_text('{}')
 bad=m.USER/'bad';bad.mkdir();(bad/'manifest.json').write_text('{"id":"bad","api":"hics-1","metadata":null}')
 state=m.scan();assert any(p['id']=='vm-fixture' for p in state['plugins']) and state['errors'];outcomes.append('bad-manifest-isolated')
 assert (m.USER/'vm-fixture/manifest.json').read_bytes()==before
 print(json.dumps({'version':subprocess.check_output(['pacman','-Q','hic-shell'],text=True).strip(),'cases':outcomes,'installedFixturePreserved':True,'realSessionUntouched':True}))
'''
p=argparse.ArgumentParser();p.add_argument('--lab',required=True,type=Path);p.add_argument('--out',required=True,type=Path);a=p.parse_args()
if a.out.exists():raise SystemExit('Choose a fresh evidence file')
args=['ssh','-i',str(a.lab/'guest_ed25519'),'-p','22280','-o','BatchMode=yes','-o','UserKnownHostsFile='+str(a.lab/'known_hosts-installed'),'root@127.0.0.1','runuser -u hics-test -- python3 -']
r=subprocess.run(args,input=REMOTE,capture_output=True,text=True,timeout=60)
if r.returncode:raise SystemExit(r.stdout+r.stderr)
report=json.loads(r.stdout);a.out.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
