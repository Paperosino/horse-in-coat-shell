#!/usr/bin/env python3
"""Run installed-only settings/work-area acceptance in a disposable CachyOS VM."""
import argparse,json,subprocess,tarfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
REMOTE=r'''
import hashlib,json,os,shutil,subprocess,tarfile,tempfile
from pathlib import Path
assert os.geteuid()==0 and Path('/etc/hostname').read_text().strip()=='hics-test'
assert subprocess.check_output(['systemd-detect-virt'],text=True).strip() in ('kvm','qemu')
package=subprocess.check_output(['pacman','-Q','hic-shell'],text=True).strip();assert package==EXPECTED,package
user=['runuser','-u','hics-test','--','env','XDG_RUNTIME_DIR=/run/user/1000','DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus']
instances=json.loads(subprocess.check_output(user+['hyprctl','instances','-j'],text=True));assert len(instances)==1,instances
instance=instances[0];user+=['WAYLAND_DISPLAY='+instance['wl_socket']]
def snapshot():
 runner=subprocess.check_output(user+['systemctl','--user','show','hic-session.service','-p','MainPID','--value'],text=True).strip()
 return {'runner':runner,'children':Path('/proc/'+runner+'/task/'+runner+'/children').read_text().strip(),'kitty':subprocess.check_output(['pgrep','-x','kitty'],text=True).strip(),'locked':json.loads(subprocess.check_output(user+['hyprctl','-i',instance['instance'],'-j','locked'],text=True)),'errors':subprocess.check_output(user+['hyprctl','-i',instance['instance'],'configerrors'],text=True).strip()}
before=snapshot();assert before['locked']=={'locked':False},'Unlock the guest through normal PAM before visual acceptance'
root=Path(tempfile.mkdtemp(prefix='hics-installed-workarea-',dir='/var/tmp'));os.chown(root,1000,1000)
preserve=False
try:
 with tarfile.open('/var/tmp/hics-workarea-tests.tar.gz') as archive:archive.extractall(root,filter='data')
 (root/'shell').symlink_to('/usr/share/hics/shell',target_is_directory=True)
 command=user+['HICS_TEST_NATIVE_DIR=/usr/share/hics/native','HICS_TEST_CAPTURE='+str(root/'capture.png'),'LANG=ru_RU.UTF-8','python3',str(root/'tests/integration_settings_workarea.py'),'--installed-runtime']
 process=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,start_new_session=True)
 try:stdout,stderr=process.communicate(timeout=120)
 except subprocess.TimeoutExpired:
  preserve=True
  raise RuntimeError('Observation timeout; inspect live worker '+str(process.pid)+' at '+str(root)+' before cleanup')
 Path('/var/tmp/hics-installed-workarea.log').write_text(stdout+stderr)
 assert process.returncode==0,stdout+stderr
 after=snapshot();assert after==before,(before,after)
 image=root/'capture.png';assert image.is_file()
 shutil.copy2(image,'/var/tmp/hics-installed-workarea.png');os.chmod('/var/tmp/hics-installed-workarea.png',0o600)
 print(json.dumps({'package':package,'installedRuntime':True,'before':before,'after':after,'passes':[line for line in stdout.splitlines() if line.startswith('PASS')],'nativeSha256':hashlib.sha256(Path('/usr/share/hics/native/hics-bars.so').read_bytes()).hexdigest(),'captureSha256':hashlib.sha256(image.read_bytes()).hexdigest(),'logPath':'/var/tmp/hics-installed-workarea.log'}))
finally:
 if not preserve:shutil.rmtree(root)
'''
p=argparse.ArgumentParser();p.add_argument('--lab',required=True,type=Path);p.add_argument('--output',required=True,type=Path);p.add_argument('--expected-package',required=True);p.add_argument('--disposable-cachyos-vm',required=True,action='store_true');a=p.parse_args()
if a.output.exists():raise SystemExit('Use a fresh evidence path')
archive=a.lab/(a.output.stem+'-tests.tar.gz')
with tarfile.open(archive,'w:gz') as bundle:
 for name in ('integration_settings_workarea.py','integration_support.py'):bundle.add(ROOT/'tests'/name,arcname='tests/'+name)
key=['-i',str(a.lab/'guest_ed25519'),'-o','BatchMode=yes','-o','ConnectTimeout=5','-o','UserKnownHostsFile='+str(a.lab/'known_hosts-installed')]
subprocess.run(['scp',*key,'-P','22280',str(archive),'root@127.0.0.1:/var/tmp/hics-workarea-tests.tar.gz'],check=True)
r=subprocess.run(['ssh',*key,'-p','22280','root@127.0.0.1','python3 -'],input='EXPECTED='+repr(a.expected_package)+'\n'+REMOTE,capture_output=True,text=True,timeout=135)
if r.returncode:raise SystemExit(r.stdout+r.stderr)
report=json.loads(r.stdout);a.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,ensure_ascii=False,indent=2))
