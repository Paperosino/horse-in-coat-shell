#!/usr/bin/env python3
"""Manage one reversible allocator experiment drop-in in the disposable guest.

Does not restart services or change production package defaults. A new guest
session is required after both applying and removing the experimental file.
"""
import argparse,json,subprocess
from pathlib import Path
REMOTE=r'''
import hashlib,json,os,stat,subprocess,tempfile
from pathlib import Path
assert os.geteuid()==0 and Path('/etc/hostname').read_text().strip()=='hics-test'
assert subprocess.check_output(['systemd-detect-virt'],text=True).strip() in ('qemu','kvm')
path=Path('/etc/systemd/user/hic-session.service.d/90-hics-lab-allocator.conf')
marker=Path('/var/tmp/hics-allocator-trial-state.json')
def read(path):
 try:fd=os.open(path,os.O_RDONLY|os.O_CLOEXEC|os.O_NOFOLLOW|os.O_NONBLOCK)
 except FileNotFoundError:return None
 with os.fdopen(fd,'rb') as stream:
  st=os.fstat(stream.fileno());assert stat.S_ISREG(st.st_mode) and st.st_uid==0 and not st.st_mode&0o022 and st.st_size<=4096
  value=stream.read(4097);assert len(value)<=4096;return value
previous=read(path);record=read(marker)
if previous is not None:
 assert record is not None,'Unowned drop-in; refuse to overwrite'
 owner=json.loads(record);accepted=owner.get('acceptedDropinSha256',[owner['dropinSha256']])
 assert hashlib.sha256(previous).hexdigest() in accepted,'Drop-in changed; preserve it for inspection'
settings={'mmap128':'MALLOC_MMAP_THRESHOLD_=131072','arena2':'MALLOC_ARENA_MAX=2','arena4':'MALLOC_ARENA_MAX=4','jemalloc-eager':'MALLOC_CONF=dirty_decay_ms:0,muzzy_decay_ms:0','jemalloc-balanced':'MALLOC_CONF=dirty_decay_ms:1000,muzzy_decay_ms:0'}
def write(path,content,mode):
 path.parent.mkdir(parents=True,exist_ok=True)
 fd,name=tempfile.mkstemp(prefix='.hics-allocator-',dir=path.parent)
 try:
  with os.fdopen(fd,'wb') as stream:os.fchmod(stream.fileno(),mode);stream.write(content);stream.flush();os.fsync(stream.fileno())
  os.replace(name,path)
 finally:
  try:os.unlink(name)
  except FileNotFoundError:pass
if PROFILE=='clear':
 path.unlink(missing_ok=True);marker.unlink(missing_ok=True)
 report={'profile':'default','dropinRemoved':not path.exists(),'requiresNewSession':True,'productionPolicy':False}
else:
 setting=settings[PROFILE]
 text=('[Service]\n# Disposable VM allocation-policy experiment; not a production default.\nEnvironment='+setting+'\n').encode()
 report={'profile':PROFILE,'setting':setting,'dropin':str(path),'dropinSha256':hashlib.sha256(text).hexdigest(),'bootBefore':Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'requiresNewSession':True,'productionPolicy':False}
 report['acceptedDropinSha256']=list(dict.fromkeys(([hashlib.sha256(previous).hexdigest()] if previous is not None else [])+[report['dropinSha256']]))
 # Write-ahead ownership permits cleanup if publishing the drop-in fails.
 write(marker,(json.dumps(report,indent=2)+'\n').encode(),0o600);write(path,text,0o644)
print(json.dumps(report))
'''
p=argparse.ArgumentParser();p.add_argument('--lab',required=True,type=Path);p.add_argument('--profile',choices=['mmap128','arena2','arena4','jemalloc-eager','jemalloc-balanced','clear'],required=True);p.add_argument('--output',required=True,type=Path);p.add_argument('--disposable-cachyos-vm',required=True,action='store_true');a=p.parse_args()
if a.output.exists():raise SystemExit('Use a fresh evidence path')
key=['-i',str(a.lab/'guest_ed25519'),'-o','BatchMode=yes','-o','ConnectTimeout=5','-o','UserKnownHostsFile='+str(a.lab/'known_hosts-installed')]
r=subprocess.run(['ssh',*key,'-p','22280','root@127.0.0.1','python3 -'],input='PROFILE='+repr(a.profile)+'\n'+REMOTE,capture_output=True,text=True,timeout=20)
if r.returncode:raise SystemExit(r.stdout+r.stderr)
report=json.loads(r.stdout);a.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
