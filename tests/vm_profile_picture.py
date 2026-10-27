#!/usr/bin/env python3
"""Check avatar pixels in a real locked disposable guest; preserve foreign files."""
import argparse,subprocess,json,shlex,time,os
from vm_cachyos import qmp
from pathlib import Path
from PIL import Image
p=argparse.ArgumentParser();p.add_argument('--lab',required=True,type=Path);p.add_argument('--out',required=True,type=Path);p.add_argument('--disposable-cachyos-vm',required=True,action='store_true')
a=p.parse_args();lab=a.lab.resolve();out=a.out.resolve();os.umask(0o077)
if (out/'avatar-result.json').exists():raise SystemExit('Choose a fresh output directory')
out.mkdir(parents=True,exist_ok=True,mode=0o700)
assert qmp(lab,'query-status')['status']=='running','Wake the existing VM before this test; do not restart it'
qmp(lab,'send-key',{'keys':[{'type':'qcode','data':'shift'}],'hold-time':35})
ssh=['ssh','-i',str(lab/'guest_ed25519'),'-p','22280','-o','BatchMode=yes','-o','ConnectTimeout=5','-o','UserKnownHostsFile='+str(lab/'known_hosts-installed'),'root@127.0.0.1']
remote=r'''
from pathlib import Path
from PIL import Image
import os,sys,subprocess,json,tempfile,hashlib,stat
assert Path('/etc/hostname').read_text().strip()=='hics-test'
assert subprocess.check_output(['systemd-detect-virt'],text=True).strip()=='kvm'
face=Path('/home/hics-test/.face');state=Path('/run/hics-avatar-probe.json');action=sys.argv[1]
def digest():
 fd=os.open(face,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
 with os.fdopen(fd,'rb') as f:
  info=os.fstat(f.fileno());assert stat.S_ISREG(info.st_mode) and info.st_size<65536,'Preserve unexpected file type/size'
  data=f.read(65536);return hashlib.sha256(data).hexdigest()
env=dict(os.environ,LANG='ru_RU.UTF-8',XDG_RUNTIME_DIR='/run/user/1000',DBUS_SESSION_BUS_ADDRESS='unix:path=/run/user/1000/bus',WAYLAND_DISPLAY='wayland-1')
def call(*args):return subprocess.check_output(['runuser','-u','hics-test','--',*args],env=env,text=True,timeout=5).strip()
if action=='begin':
 assert not os.path.lexists(face),'Preserve pre-existing avatar'
 assert not state.exists(),'Another avatar test is active'
 data={'pid':call('pgrep','-x','hics-qs'),'hash':None};os.umask(0o077);state.write_text(json.dumps(data))
 call('/usr/share/hics/qs/bin/hics-qs','ipc','-p','/usr/share/hics/shell','call','lock','lock')
else:
 data=json.loads(state.read_text());assert call('pgrep','-x','hics-qs')==data['pid'],'Shell changed during test'
 if action in ('red','blue'):
  assert not os.path.lexists(face) or digest()==data['hash'],'Preserve unexpected file'
  fd,name=tempfile.mkstemp(prefix='.hics-avatar-probe-',dir=face.parent);os.close(fd)
  try:
   Image.new('RGB',(24,16),action).save(name,format='BMP');os.chown(name,1000,1000);os.chmod(name,0o644);os.replace(name,face)
  finally:Path(name).unlink(missing_ok=True)
  data['hash']=digest();state.write_text(json.dumps(data))
 elif action=='cleanup':
  if os.path.lexists(face):
   assert digest()==data['hash'],'Preserve unexpected avatar';face.unlink()
  state.unlink()
assert call('/usr/share/hics/qs/bin/hics-qs','ipc','-p','/usr/share/hics/shell','call','lock','isLocked')=='true'
print(json.dumps({'pid':data['pid'],'stage':action,'locked':True}))
'''
def step(action):
 r=subprocess.run(ssh+['python3 - '+shlex.quote(action)],input=remote,text=True,capture_output=True,timeout=12);assert r.returncode==0,r.stderr;return json.loads(r.stdout)
def capture(stage,colour=None):
 for _ in range(35):
  ppm=out/('avatar-'+stage+'.ppm');qmp(lab,'screendump',{'filename':str(ppm)});im=Image.open(ppm).convert('RGB');r,g,b=im.getpixel((im.width//2,round(im.height*.56)))
  valid=(r>180 and g<70 and b<70) if colour=='red' else (b>180 and r<70 and g<70) if colour=='blue' else not (r>180 and g<70 and b<70) and not (b>180 and r<70 and g<70)
  if valid:im.save(out/('avatar-'+stage+'.png'));return [r,g,b]
  time.sleep(.2)
 raise AssertionError('Expected avatar colour did not appear: '+stage)
report={};started=False
try:
 report['begin']=step('begin');started=True
 for colour in ('red','blue'):
  report[colour]=step(colour);report[colour]['pixel']=capture(colour,colour)
finally:
 if started:report['cleanup']=step('cleanup')
report['cleanup']['pixel']=capture('fallback');(out/'avatar-result.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
