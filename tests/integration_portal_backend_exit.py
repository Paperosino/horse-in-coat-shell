#!/usr/bin/env python3
"""Request normal teardown of the instrumented, test-only backend in CachyOS VM.

This controller never signals or restarts a service. The Exit object must be
compiled only into the disposable diagnostic copy, not into a release package.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import select
import subprocess
import time
from gi.repository import Gio, GLib

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--expected-executable',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--disposable-cachyos-vm',action='store_true',required=True)
    args=parser.parse_args()
    assert os.getuid()==1000 and Path('/etc/hostname').read_text().strip()=='hics-test'
    assert subprocess.check_output(['systemd-detect-virt'],text=True).strip() in ('kvm','qemu')
    assert not args.output.exists();os.umask(0o077);args.output.parent.mkdir(parents=True,exist_ok=True)
    policy=subprocess.check_output(['systemctl','--user','show','xdg-desktop-portal-hyprland.service','-p','Type','-p','Restart'],text=True)
    policy=dict(line.split('=',1) for line in policy.splitlines() if '=' in line)
    assert policy.get('Type')=='exec' and policy.get('Restart')=='no','Use the diagnostic Type=exec,Restart=no override so service teardown cannot truncate sanitizer review'
    bus=Gio.bus_get_sync(Gio.BusType.SESSION,None)
    backend='org.freedesktop.impl.portal.desktop.hyprland'
    def call(target,path,interface,method,parameters=None):
        return bus.call_sync(target,path,interface,method,parameters,None,Gio.DBusCallFlags.NONE,3000,None).unpack()
    call(backend,'/org/freedesktop/portal/desktop','org.freedesktop.DBus.Properties','Get',GLib.Variant('(ss)',('org.freedesktop.impl.portal.ScreenCast','version')))
    owner,=call('org.freedesktop.DBus','/org/freedesktop/DBus','org.freedesktop.DBus','GetNameOwner',GLib.Variant('(s)',(backend,)))
    pid,=call('org.freedesktop.DBus','/org/freedesktop/DBus','org.freedesktop.DBus','GetConnectionUnixProcessID',GLib.Variant('(s)',(owner,)))
    process=Path('/proc')/str(pid)
    assert (process/'exe').resolve()==args.expected_executable.resolve()
    with args.expected_executable.open('rb') as stream:sha=hashlib.file_digest(stream,'sha256').hexdigest()
    environment=dict(item.split('=',1) for item in (process/'environ').read_bytes().decode().split('\0') if '=' in item)
    assert 'detect_leaks=1' in environment.get('ASAN_OPTIONS','')
    assert 'suppressions' not in environment.get('ASAN_OPTIONS','')+environment.get('LSAN_OPTIONS','')
    assert 'libasan.so' in (process/'maps').read_text()
    report={'status':'running','backendPid':pid,'backendSha256':sha,'releaseBackend':False,'serviceType':policy['Type'],'restartPolicy':policy['Restart'],'exitReplyReturned':False,'asanOptions':environment.get('ASAN_OPTIONS'),'lsanOptions':environment.get('LSAN_OPTIONS',''),'asanMapped':True}
    def save():
        pending=args.output.with_suffix('.pending');pending.write_text(json.dumps(report,indent=2)+'\n');pending.replace(args.output)
    save();identity=os.pidfd_open(pid);begin=time.monotonic()
    try:
        call(backend,'/org/hics/TestPortal','org.hics.TestPortal','Exit')
        report['exitReplyReturned']=True;save()
        assert select.select([identity],[],[],10)[0],'Backend did not finish teardown'
        report['processExited']=True;report['exitSeconds']=round(time.monotonic()-begin,3)
        # Exiting is not a clean sanitizer result. The parent/systemd status and
        # complete journal are separate mandatory evidence for acceptance.
        report['status']='exited-awaiting-sanitizer-review'
    except BaseException as error:
        report['status']='failed';report['errorType']=type(error).__name__;raise
    finally:os.close(identity);save()
    print(json.dumps(report,indent=2))
if __name__=='__main__':main()
