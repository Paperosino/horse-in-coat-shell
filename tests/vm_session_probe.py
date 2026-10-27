#!/usr/bin/env python3
"""Read authoritative main-session evidence in the disposable CachyOS guest."""
import argparse,json,subprocess
from pathlib import Path
REMOTE=r'''
import json,subprocess,hashlib
from pathlib import Path
assert Path('/etc/hostname').read_text().strip()=='hics-test'
assert subprocess.check_output(['systemd-detect-virt'],text=True).strip() in ('kvm','qemu')
user=['runuser','-u','hics-test','--','env','XDG_RUNTIME_DIR=/run/user/1000','DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus','LANG=ru_RU.UTF-8']
def u(*args):return subprocess.check_output(user+list(args),text=True,timeout=10).strip()
instances=json.loads(u('hyprctl','instances','-j'));assert len(instances)==1,instances
instance=instances[0];user+=['WAYLAND_DISPLAY='+instance['wl_socket']];compositor=instance['pid']
runner=int(u('systemctl','--user','show','hic-session.service','-p','MainPID','--value'))
children=Path(f'/proc/{runner}/task/{runner}/children').read_text().split()
uis=[int(pid) for pid in children if Path('/proc/'+pid+'/comm').read_text().strip()=='hics-qs'];assert len(uis)==1,uis
path=Path('/usr/share/hics/native/hics-bars.so');entries=[line for line in Path(f'/proc/{compositor}/maps').read_text().splitlines() if str(path) in line]
assert entries and all(int(line.split()[4])==path.stat().st_ino for line in entries),entries
native=hashlib.sha256(path.read_bytes()).hexdigest();assert native==EXPECTED_NATIVE,native
assert not u('hyprctl','-i',instance['instance'],'configerrors')
health=u('/usr/share/hics/qs/bin/hics-qs','ipc','-p','/usr/share/hics/shell','call','sessionHealth','ready');assert health=='true',health
state=json.loads(Path('/home/hics-test/.local/state/hics/shell-recovery.json').read_text());assert state.get('safe') is False,state
package=subprocess.check_output(['pacman','-Q','hic-shell'],text=True).strip();assert package==EXPECTED_PACKAGE,package
config=Path('/usr/share/hics/qml/Hyprstack/lib/libhyprstack-config.so')
configEntries=[line for line in Path(f'/proc/{uis[0]}/maps').read_text().splitlines() if str(config) in line]
assert configEntries and all(int(line.split()[4])==config.stat().st_ino for line in configEntries),configEntries
configHash=hashlib.sha256(config.read_bytes()).hexdigest()
if EXPECTED_CONFIG:assert configHash==EXPECTED_CONFIG,configHash
services=Path('/usr/share/hics/qml/Hyprstack/lib/libhyprstack-services.so')
serviceEntries=[line for line in Path(f'/proc/{uis[0]}/maps').read_text().splitlines() if str(services) in line]
assert serviceEntries and all(int(line.split()[4])==services.stat().st_ino for line in serviceEntries),serviceEntries
servicesHash=hashlib.sha256(services.read_bytes()).hexdigest()
if EXPECTED_SERVICES:assert servicesHash==EXPECTED_SERVICES,servicesHash
boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip();assert not PREVIOUS_BOOT or boot!=PREVIOUS_BOOT
report={'boot':boot,'package':package,'compositor':compositor,'runner':runner,'ui':uis[0],'health':health,'nativeSha256':native,'nativeInodeMatchesLoadedModule':True,'configSha256':configHash,'configInodeMatchesLoadedModule':True,'servicesSha256':servicesHash,'servicesInodeMatchesLoadedModule':True,'safeMode':state['safe'],'restarts':u('systemctl','--user','show','hic-session.service','-p','NRestarts','--value'),'locked':json.loads(u('hyprctl','-i',instance['instance'],'-j','locked')),'bindCount':len(json.loads(u('hyprctl','-i',instance['instance'],'-j','binds'))),'configerrors':'','userFailed':u('systemctl','--user','--failed','--no-legend'),'systemFailed':subprocess.check_output(['systemctl','--failed','--no-legend'],text=True).strip()}
assert report['restarts']=='0' and not report['userFailed'] and not report['systemFailed'],report
print(json.dumps(report))
'''
p=argparse.ArgumentParser();p.add_argument('--lab',required=True,type=Path);p.add_argument('--output',required=True,type=Path);p.add_argument('--expected-package',required=True);p.add_argument('--expected-native-sha256',required=True);p.add_argument('--expected-config-sha256',default='');p.add_argument('--expected-services-sha256',default='');p.add_argument('--previous-boot',default='');p.add_argument('--disposable-cachyos-vm',required=True,action='store_true');a=p.parse_args()
if a.output.exists():raise SystemExit('Use a fresh evidence path')
key=['-i',str(a.lab/'guest_ed25519'),'-o','BatchMode=yes','-o','ConnectTimeout=5','-o','UserKnownHostsFile='+str(a.lab/'known_hosts-installed')]
r=subprocess.run(['ssh',*key,'-p','22280','root@127.0.0.1','python3 -'],input='EXPECTED_PACKAGE='+repr(a.expected_package)+'\nEXPECTED_NATIVE='+repr(a.expected_native_sha256)+'\nEXPECTED_SERVICES='+repr(a.expected_services_sha256)+'\nEXPECTED_CONFIG='+repr(a.expected_config_sha256)+'\nPREVIOUS_BOOT='+repr(a.previous_boot)+'\n'+REMOTE,capture_output=True,text=True,timeout=45)
if r.returncode:raise SystemExit(r.stdout+r.stderr)
report=json.loads(r.stdout);a.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
