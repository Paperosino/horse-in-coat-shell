#!/usr/bin/env python3
"""Real bounded tmpfs exhaustion, disposable guest only, isolated helper profile."""
import argparse,hashlib,json,subprocess,tarfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
WORKER=r'''
import errno,hashlib,json,os,socket,subprocess,sys,time
from pathlib import Path
assert os.getuid()==1000
root=Path(sys.argv[1]);env=dict(os.environ,XDG_CONFIG_HOME=str(root/'config'),XDG_STATE_HOME=str(root/'state'),XDG_DATA_HOME=str(root/'data'),XDG_CACHE_HOME=str(root/'cache'),XDG_RUNTIME_DIR=str(root/'runtime'),PYTHONDONTWRITEBYTECODE='1')
env.pop('HYPRLAND_INSTANCE_SIGNATURE',None)
config=root/'config/hics';config.mkdir(parents=True);state=root/'state/hics';state.mkdir()
log=(root/'daemon.log').open('w');daemon=subprocess.Popen([sys.executable,str(root/'assets/configuration_manager.py'),'watch'],env=env,stdout=log,stderr=subprocess.STDOUT)
try:
 def call():
  for _ in range(100):
   assert daemon.poll() is None,(root/'daemon.log').read_text()
   endpoints=list((root/'runtime').glob('hics-configuration-*/control.sock'))
   if endpoints:break
   time.sleep(.05)
  assert endpoints
  with socket.socket(socket.AF_UNIX) as client:
   client.settimeout(3);client.connect(str(endpoints[0]));client.sendall(b'{"operation":"status"}\n');raw=b''
   while b'\n' not in raw:
    part=client.recv(65536);assert part;raw+=part
   return json.loads(raw)
 assert 'error' not in call()
 filler=state/'fill.bin';written=0;failure=None
 with filler.open('wb',buffering=0) as stream:
  while written<=3*1024*1024:
   try:written+=stream.write(b'x'*65536)
   except OSError as error:failure=error.errno;break
 assert failure==errno.ENOSPC and written<=2*1024*1024
 (config/'configuration-history.json').write_text('{"keep":0}');time.sleep(1.5)
 result=call();assert 'error' not in result and 'No space left' in result['recoveryWarning'],result
 def writes():
  return int(next(line.split(':')[1] for line in Path('/proc/'+str(daemon.pid)+'/io').read_text().splitlines() if line.startswith('syscw:')))
 time.sleep(1);before=writes();time.sleep(2.2);after=writes()
 assert after==before,{'idleWriteCallsBefore':before,'idleWriteCallsAfter':after,'log':(root/'daemon.log').read_text()}
 filler.unlink();(config/'configuration-history.json').write_text('{}');time.sleep(1.5)
 call();result=call();assert result['settingsValid'] and 'No space left' not in result['recoveryWarning'],result
 print(json.dumps({'errno':failure,'filesystemBytes':os.statvfs(state).f_blocks*os.statvfs(state).f_frsize,'filledBytes':written,'sameDaemon':daemon.poll() is None,'idleWriteCalls':after-before,'recoveredWithoutRestart':True,'serviceSourceSha256':hashlib.sha256((root/'assets/configuration_manager.py').read_bytes()).hexdigest()}))
finally:
 daemon.terminate()
 try:daemon.wait(timeout=5)
 except subprocess.TimeoutExpired:daemon.kill();daemon.wait()
 log.close()
'''
REMOTE=r'''
import hashlib,json,os,shutil,subprocess,sys,tarfile,tempfile
from pathlib import Path
assert os.geteuid()==0 and Path('/etc/hostname').read_text().strip()=='hics-test'
assert subprocess.check_output(['systemd-detect-virt'],text=True).strip() in ('kvm','qemu')
archive=Path('/var/tmp/hics-enospc-sources.tar.gz')
with archive.open('rb') as stream:source_hash=hashlib.file_digest(stream,'sha256').hexdigest()
root=Path(tempfile.mkdtemp(prefix='hics-real-enospc-',dir='/var/tmp'));os.chown(root,1000,1000)
for name in ('state','runtime'):
 path=root/name;path.mkdir();os.chown(path,1000,1000);path.chmod(0o700)
with tarfile.open(archive) as bundle:bundle.extractall(root/'assets',filter='data')
if USE_INSTALLED:
 shutil.rmtree(root/'assets');(root/'assets').symlink_to('/usr/share/hics/shell/assets',target_is_directory=True)
worker=root/'worker.py';worker.write_text(WORKER);worker.chmod(0o644)
subprocess.run(['mount','-t','tmpfs','-o','size=2M,mode=0700,uid=1000,gid=1000','hics-enospc-test',str(root/'state')],check=True)
process=subprocess.Popen(['runuser','-u','hics-test','--','python3',str(worker),str(root)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
try:stdout,stderr=process.communicate(timeout=60)
except subprocess.TimeoutExpired:
 print(json.dumps({'runningWorker':process.pid,'mountedAt':str(root/'state'),'sourceSha256':source_hash}),flush=True)
 raise RuntimeError('Inspect this running worker before cleanup; no restart attempted')
try:
 assert process.returncode==0,stdout+stderr
 report=json.loads(stdout);report['sourceSha256']=source_hash;report['sourceMode']='installed' if USE_INSTALLED else 'snapshot';report['package']=subprocess.check_output(['pacman','-Q','hic-shell'],text=True).strip();print(json.dumps(report))
finally:
 subprocess.run(['umount',str(root/'state')],check=True);shutil.rmtree(root)
'''
p=argparse.ArgumentParser();p.add_argument('--lab',required=True,type=Path);p.add_argument('--out',required=True,type=Path);p.add_argument('--disposable-cachyos-vm',required=True,action='store_true');p.add_argument('--installed',action='store_true');a=p.parse_args()
if a.out.exists():raise SystemExit('Choose a fresh evidence file')
archive=a.lab/(a.out.stem+'-sources.tar.gz')
with tarfile.open(archive,'w:gz') as bundle:
 for path in sorted((ROOT/'shell/assets').glob('*.py')):bundle.add(path,arcname=path.name)
 bundle.add(ROOT/'shell/assets/feature_data',arcname='feature_data')
key=['-i',str(a.lab/'guest_ed25519'),'-o','UserKnownHostsFile='+str(a.lab/'known_hosts-installed')]
subprocess.run(['scp',*key,'-P','22280',str(archive),'root@127.0.0.1:/var/tmp/hics-enospc-sources.tar.gz'],check=True)
r=subprocess.run(['ssh',*key,'-p','22280','root@127.0.0.1','python3 -'],input='WORKER='+repr(WORKER)+'\nUSE_INSTALLED='+repr(a.installed)+'\n'+REMOTE,capture_output=True,text=True,timeout=75)
if r.returncode:raise SystemExit(r.stdout+r.stderr)
report=json.loads(r.stdout);assert report['serviceSourceSha256']==hashlib.sha256((ROOT/'shell/assets/configuration_manager.py').read_bytes()).hexdigest();a.out.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
