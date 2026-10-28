#!/usr/bin/env python3
"""Verified QMP clicks in the fixed disposable guest; no host input control.

A compositor can warp its cursor while QEMU retains its last absolute device
position. Resending identical axes then emits no motion. Always move away and
back, and read actual compositor coordinates before pressing a button.
"""
import argparse
import json
from pathlib import Path
import shlex
import subprocess
import time
from vm_cachyos import qmp


def click_guest(lab, x, y, *, ssh_port=22280, identity=None, known_hosts=None, button='left'):
    lab = Path(lab).resolve()
    assert button in ('left','right') and 0<=x<1280 and 0<=y<800
    def remote(arguments):
        command = ['ssh','-i',str(identity or lab/'guest_ed25519'),'-p',str(ssh_port),
            '-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-o','ConnectTimeout=5',
            '-o','UserKnownHostsFile='+str(known_hosts or lab/'known_hosts-installed'),
            'root@127.0.0.1',shlex.join(arguments)]
        return subprocess.check_output(command,text=True,timeout=10).strip()
    assert remote(['cat','/etc/hostname'])=='hics-test'
    assert remote(['systemd-detect-virt']) in ('kvm','qemu')
    user = ['runuser','-u','hics-test','--','env','XDG_RUNTIME_DIR=/run/user/1000','hyprctl','-i','0']
    monitors = json.loads(remote(user+['monitors','-j']))
    assert len(monitors)==1 and all(monitors[0].get(k)==v for k,v in
        {'width':1280,'height':800,'scale':1,'transform':0,'x':0,'y':0}.items()), 'Inspect unsupported guest geometry'
    assert not json.loads(remote(user+['-j','locked']))['locked'], 'Unlock normally before UI actions'
    assert qmp(lab,'query-status').get('running')
    before = json.loads(remote(user+['cursorpos','-j']))
    for px,py in (((x+31)%1280,(y+31)%800),(x,y)):
        qmp(lab,'input-send-event',{'events':[
            {'type':'abs','data':{'axis':'x','value':round(px/1280*32767)}},
            {'type':'abs','data':{'axis':'y','value':round(py/800*32767)}}]})
        time.sleep(.12)
    actual = json.loads(remote(user+['cursorpos','-j']))
    assert abs(actual['x']-x)<=1 and abs(actual['y']-y)<=1, {'expected':(x,y),'actual':actual}
    try:
        qmp(lab,'input-send-event',{'events':[{'type':'btn','data':{'button':button,'down':True}}]})
        time.sleep(.12)
    finally:
        qmp(lab,'input-send-event',{'events':[{'type':'btn','data':{'button':button,'down':False}}]})
    return {'target':[x,y],'button':button,'before':before,'verifiedPositionBeforePress':actual}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--lab',type=Path,required=True)
    p.add_argument('--x',type=int,required=True);p.add_argument('--y',type=int,required=True)
    p.add_argument('--ssh-port',type=int,default=22280)
    p.add_argument('--identity',type=Path);p.add_argument('--known-hosts',type=Path)
    p.add_argument('--button',choices=('left','right'),default='left')
    p.add_argument('--disposable-cachyos-vm',action='store_true',required=True)
    a=p.parse_args()
    print(json.dumps(click_guest(a.lab,a.x,a.y,ssh_port=a.ssh_port,identity=a.identity,
        known_hosts=a.known_hosts,button=a.button),indent=2))
