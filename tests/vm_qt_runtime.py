#!/usr/bin/env python3
"""Run prepared private Qt regression payload in the disposable CachyOS guest.

Does not replace installed libraries, reload plugins or restart the shell.
Payload binaries are cross-built against the same Qt/glibc ABI; its manifest
is checked again in the guest. Authentication is deliberately separate.
"""
import argparse
import json
from pathlib import Path
import subprocess

WORKER=r'''
import hashlib,json,os,subprocess,sys,time
from pathlib import Path
assert os.getuid()==1000
assert Path('/etc/hostname').read_text().strip()=='hics-test'
assert subprocess.check_output(['systemd-detect-virt'],text=True).strip() in ('qemu','kvm')
root=Path(PAYLOAD_ROOT);assert root.parent==Path('/var/tmp') and root.name.startswith('hics-qt')
out=root/'evidence'
m=json.loads((root/'manifest.json').read_text())
for p,h in m['files'].items():assert hashlib.sha256((root/'bin'/p).read_bytes()).hexdigest()==h,p
if not INSTALLED_RUNTIME:
 for p,h in m['overlay'].items():assert hashlib.sha256((root/'overlay'/p).read_bytes()).hexdigest()==h,p
else:
 runtime=Path('/usr/share/hics/qs');metadata=json.loads((runtime/'hics-qt-patches.json').read_text())
 for p,h in metadata['files'].items():assert hashlib.sha256((runtime/p).read_bytes()).hexdigest()==h,p
 for p,target in metadata['symlinks'].items():assert (runtime/p).is_symlink() and os.readlink(runtime/p)==target,p
def state():
 runner=int(subprocess.check_output(['systemctl','--user','show','hic-session.service','-p','MainPID','--value'],text=True))
 children=Path(f'/proc/{runner}/task/{runner}/children').read_text().split()
 ui=[int(p) for p in children if Path('/proc/'+p+'/comm').read_text().strip()=='hics-qs'];assert len(ui)==1,ui
 locked=json.loads(subprocess.check_output(['hyprctl','-i','0','-j','locked'],text=True))['locked']
 return {'runner':runner,'ui':ui[0],'boot':Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'locked':locked,
 'configerrors':subprocess.check_output(['hyprctl','-i','0','configerrors'],text=True).strip()}
before=state();assert not before['locked'] and not before['configerrors'],before
assert subprocess.check_output(['hyprctl','-i','0','submap'],text=True).strip()!='hics-onboarding','Finish or skip the first-run tour normally before nested compositor tests'
progress=out/'worker.json';assert not progress.exists(),'Inspect prior evidence before starting another worker'
record={'pid':os.getpid(),'before':before,'cases':[],'status':'running'}
def save():progress.write_text(json.dumps(record,indent=2)+'\n')
save()
def run(name,argv,env=None,timeout=40):
 start=time.monotonic()
 with (out/(name+'-command.log')).open('w') as log:
  p=subprocess.run(argv,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=timeout)
 record['cases'].append({'name':name,'returncode':p.returncode,'seconds':round(time.monotonic()-start,3)})
 save();assert p.returncode==0,(name,(out/(name+'-command.log')).read_text()[-3000:])
try:
 tests=root/'tests';runtime=Path('/usr/share/hics/qs');overlay=runtime if INSTALLED_RUNTIME else root/'overlay';binary=root/'bin';overlay_args=[] if INSTALLED_RUNTIME else ['--qt-overlay',str(overlay)]
 if 'sql-drivers-probe' in m['files']:
  sqlenv=dict(os.environ,LD_LIBRARY_PATH=str(overlay/'lib')+':'+str(runtime/'lib'))
  run('sql-drivers',[str(binary/'sql-drivers-probe'),str(runtime/'lib/qt6/plugins')],env=sqlenv)
  sql=json.loads((out/'sql-drivers-command.log').read_text())
  assert sql['loaded']==['QIBASE','QMYSQL','QODBC','QPSQL','QSQLITE'] and sql['sqliteFts5'] and not sql['externalConnections'],sql
 run('portal',['python3',str(tests/'diagnose_qt_portal_registration.py'),'--runtime',str(overlay),'--probe-binary',str(binary/'portal-probe'),'--output',str(out/'portal.json')])
 run('portal-frontend',['python3',str(tests/'integration_qt_portal_frontend.py'),'--runtime',str(overlay),'--probe-binary',str(binary/'portal-probe'),'--output',str(out/'portal-frontend.json')])
 run('audio',['python3',str(tests/'diagnose_qt_multimedia.py'),'--runtime',str(runtime),*overlay_args,'--asan','--probe-binary',str(binary/'multimedia-probe'),'--output',str(out/'audio.json')])
 for name,extra in [('input',[]),('input-no-ime',['--without-ime'])]:
  run(name,['python3',str(tests/'integration_qt_text_input.py'),'--runtime',str(runtime),*overlay_args,'--keyboard-binary',str(binary/'keyboard-probe'),'--output',str(out/(name+'.json')),*extra],timeout=50)
 video=out/'video-context';video.mkdir();(video/'run').mkdir(mode=0o700)
 env=dict(os.environ,HOME=str(video),XDG_RUNTIME_DIR=str(video/'run'),XDG_CONFIG_HOME=str(video/'config'),XDG_DATA_HOME=str(video/'data'),XDG_STATE_HOME=str(video/'state'),XDG_CACHE_HOME=str(video/'cache'),
  DBUS_SESSION_BUS_ADDRESS='unix:path='+str(video/'absent-bus'),DBUS_SYSTEM_BUS_ADDRESS='unix:path='+str(video/'absent-bus'),QT_QPA_PLATFORM='offscreen',QT_QPA_PLATFORMTHEME='',QT_FORCE_STDERR_LOGGING='1',
  LD_LIBRARY_PATH=str(overlay/'lib')+':'+str(runtime/'lib'),QT_PLUGIN_PATH=str(overlay/'plugins')+':'+str(runtime/'lib/qt6/plugins'),PIPEWIRE_REMOTE='hics-video-absent',PULSE_SERVER='unix:'+str(video/'absent-pulse'))
 for key in ('QT_FFMPEG_DECODING_HW_DEVICE_TYPES','QT_FFMPEG_ENCODING_HW_DEVICE_TYPES'):env.pop(key,None)
 for name,extra in [('video',[]),('video-watchdog',['watchdog'])]:
  run(name,[str(binary/'wallpaper-probe'),str(binary/'wallpaper-loop.mp4'),*extra],env=env,timeout=45)
  lines=(out/(name+'-command.log')).read_text().splitlines();data=next(json.loads(line) for line in lines if line.startswith('{'))
  assert data['frames']>0 and data['colorful'] and not data['error'],data
  if extra:assert data['sinkDetached'] and 1<=data['recoveries']<=2,data
  else:assert data['frames']>18 and data['pausedStable'] and data['recoveries']==0,data
  (out/(name+'.json')).write_text(json.dumps(data,indent=2)+'\n')
 record['after']=state();assert record['after']==before,record
 record['status']='passed';save();print(json.dumps(record,indent=2))
except BaseException:
 record['status']='failed';save();raise
'''

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--lab',required=True,type=Path)
    p.add_argument('--output',required=True,type=Path)
    p.add_argument('--payload-root',type=Path,default=Path('/var/tmp/hics-qt109'))
    p.add_argument('--ssh-port', type=int, default=22280)
    p.add_argument('--identity', type=Path)
    p.add_argument('--known-hosts', type=Path)
    p.add_argument('--installed-runtime',action='store_true',help='Verify installed manifest and exercise installed Qt, without the private overlay')
    p.add_argument('--disposable-cachyos-vm',required=True,action='store_true')
    args=p.parse_args()
    if args.output.exists():p.error('Use a fresh evidence path')
    lab=args.lab
    command=['ssh','-i',str(args.identity or lab/'guest_ed25519'),'-p',str(args.ssh_port),'-o','BatchMode=yes','-o','ConnectTimeout=5','-o','UserKnownHostsFile='+str(args.known_hosts or lab/'known_hosts-installed'),
        'root@127.0.0.1','systemd-inhibit --what=idle:sleep --mode=block --who=hics-tests --why=qt-runtime-regression runuser -u hics-test -- env XDG_RUNTIME_DIR=/run/user/1000 DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus WAYLAND_DISPLAY=wayland-1 python3 -']
    if args.payload_root.parent!=Path('/var/tmp') or not args.payload_root.name.startswith('hics-qt'):p.error('Only a prepared disposable guest payload is supported')
    result=subprocess.run(command,input='PAYLOAD_ROOT='+repr(str(args.payload_root))+'\nINSTALLED_RUNTIME='+repr(args.installed_runtime)+'\n'+WORKER,capture_output=True,text=True,timeout=190)
    if result.returncode:raise SystemExit(result.stdout+result.stderr)
    report=json.loads(result.stdout);args.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))

if __name__=='__main__':main()
