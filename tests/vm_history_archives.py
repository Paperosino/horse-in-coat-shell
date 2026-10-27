#!/usr/bin/env python3
"""Installed history reader, old guest archives read-only, private new profile."""
import argparse,hashlib,json,subprocess
from pathlib import Path
REMOTE=r'''
import gzip,hashlib,json,os,subprocess,sys,tempfile
from pathlib import Path
assert os.getuid()==1000 and Path('/etc/hostname').read_text().strip()=='hics-test'
assert subprocess.check_output(['systemd-detect-virt'],text=True).strip() in ('kvm','qemu')
old=Path.home()/'.local/state/hics/configuration-history'
with tempfile.TemporaryDirectory(prefix='hics-history-installed-') as directory:
 root=Path(directory)
 for key in ('CONFIG','DATA','STATE','CACHE'):os.environ['XDG_'+key+'_HOME']=str(root/key.lower())
 sys.path.insert(0,'/usr/share/hics/shell/assets');import configuration_manager as m
 previous=list(old.glob('*.json.gz'));assert previous,'No old archives to check'
 for path in previous:m.load_snapshot(path)
 ident=m.snapshot('Installed test');path=m.HISTORY/(ident+'.json.gz');raw=path.read_bytes();assert m.load_snapshot(path)['id']==ident
 document=json.loads(gzip.decompress(raw));document['files']['dock.json']='{"enabled":false}'
 path.write_bytes(gzip.compress(json.dumps(document).encode()))
 try:m.load_snapshot(path)
 except ValueError as error:assert 'checksum' in str(error)
 else:raise AssertionError('Altered payload accepted')
 path.write_bytes(gzip.compress(b'')*1000+raw)
 try:m.load_snapshot(path)
 except ValueError as error:assert 'gzip member' in str(error)
 else:raise AssertionError('Concatenated stream accepted')
 path.write_bytes(raw);assert len(m.history())==1
 print(json.dumps({'version':subprocess.check_output(['pacman','-Q','hic-shell'],text=True).strip(),'oldArchivesRead':len(previous),'newSnapshotValid':True,'changedPayloadRejected':True,'concatenationRejected':True,'realProfileUnchanged':True,'sourceSha256':hashlib.sha256(Path(m.__file__).read_bytes()).hexdigest()}))
'''
p=argparse.ArgumentParser();p.add_argument('--lab',required=True,type=Path);p.add_argument('--out',required=True,type=Path);a=p.parse_args()
if a.out.exists():raise SystemExit('Choose a fresh evidence file')
cmd=['ssh','-i',str(a.lab/'guest_ed25519'),'-p','22280','-o','UserKnownHostsFile='+str(a.lab/'known_hosts-installed'),'root@127.0.0.1','runuser -u hics-test -- python3 -']
r=subprocess.run(cmd,input=REMOTE,capture_output=True,text=True,timeout=60)
if r.returncode:raise SystemExit(r.stdout+r.stderr)
report=json.loads(r.stdout);assert report['sourceSha256']==hashlib.sha256((Path(__file__).resolve().parents[1]/'shell/assets/configuration_manager.py').read_bytes()).hexdigest();a.out.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
