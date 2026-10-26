#!/usr/bin/env python3
"""Private CachyOS fault-injection VM; no host devices or shared directories."""
import argparse, hashlib, json, os, shutil, socket, subprocess, time
from pathlib import Path


def qmp(lab,execute,arguments=None):
    with socket.socket(socket.AF_UNIX) as client:
        client.settimeout(5);client.connect(str(lab/'qmp.sock'));stream=client.makefile('rwb',buffering=0)
        json.loads(stream.readline())
        for command in [{'execute':'qmp_capabilities'},{'execute':execute,**({'arguments':arguments} if arguments else {})}]:
            stream.write(json.dumps(command).encode()+b'\n')
            while True:
                reply=json.loads(stream.readline())
                if 'error' in reply:raise RuntimeError(reply['error'])
                if 'return' in reply:break
        return reply['return']


def main():
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['start','status','stop'])
    parser.add_argument('--lab',type=Path,required=True);parser.add_argument('--installed',action='store_true');args=parser.parse_args()
    os.umask(0o077);lab=args.lab.resolve();lab.mkdir(parents=True,exist_ok=True);lab.chmod(0o700)
    if args.action!='start':
        print(json.dumps(qmp(lab,'query-status' if args.action=='status' else 'quit')));return
    try:qmp(lab,'query-status')
    except (FileNotFoundError,ConnectionRefusedError):pass
    else:raise SystemExit('VM is already running; do not restart it')
    iso=lab/'cachyos-desktop-linux-260809.iso'
    expected=(lab/(iso.name+'.sha256')).read_text().split()[0]
    with iso.open('rb') as stream:
        digest=hashlib.file_digest(stream,'sha256').hexdigest()
    if digest!=expected:raise SystemExit('ISO SHA256 mismatch')
    for name in ('system.qcow2','uefi-vars.fd','vmlinuz','initramfs.img'):
        path=lab/name
        if path.is_symlink():raise SystemExit('VM assets must not be symlinks: '+name)
    disk=lab/'system.qcow2'
    if not disk.exists():subprocess.run(['qemu-img','create','-f','qcow2',str(disk),'60G'],check=True)
    if not (lab/'uefi-vars.fd').exists():shutil.copyfile('/usr/share/edk2/x64/OVMF_VARS.4m.fd',lab/'uefi-vars.fd')
    argv=['qemu-system-x86_64','-name','hics-cachyos-stability','-accel','kvm','-cpu','host','-smp','2','-m','4096',
          '-nodefaults','-device','virtio-vga','-display','none','-device','virtio-rng-pci',
          '-drive','if=pflash,format=raw,readonly=on,file=/usr/share/edk2/x64/OVMF_CODE.4m.fd',
          '-drive','if=pflash,format=raw,file='+str(lab/'uefi-vars.fd'),
          '-drive','if=virtio,format=qcow2,file='+str(disk),'-drive','if=virtio,format=raw,readonly=on,file='+str(iso),
          '-netdev','user,id=net0,hostfwd=tcp:127.0.0.1:22280-:22','-device','virtio-net-pci,netdev=net0',
          '-qmp','unix:'+str(lab/'qmp.sock')+',server=on,wait=off',
          '-chardev','socket,id=serial0,path='+str(lab/'serial.sock')+',server=on,wait=off,logfile='+str(lab/'serial.log'),
          '-device','isa-serial,chardev=serial0']
    if args.installed:
        iso_index=argv.index('if=virtio,format=raw,readonly=on,file='+str(iso))
        del argv[iso_index-1:iso_index+1]
    else:
        argv.extend(['-kernel',str(lab/'vmlinuz'),'-initrd',str(lab/'initramfs.img'),
          '-append','archisobasedir=arch archisosearchuuid=2026-08-09-15-47-03-00 cow_spacesize=2G copytoram=n console=ttyS0,115200 systemd.unit=multi-user.target systemd.debug_shell=ttyS0 systemd.mask=serial-getty@ttyS0.service systemd.mask=systemd-firstboot.service systemd.mask=systemd-time-wait-sync.service'])
    with (lab/'qemu.log').open('ab') as log:
        child=subprocess.Popen(['nice','-n','5',*argv],stdout=log,stderr=log,start_new_session=True)
    (lab/'vm.json').write_text(json.dumps({'pid':child.pid,'isoSha256':digest,'created':time.time(),'argv':argv},indent=2))
    print(json.dumps({'pid':child.pid,'lab':str(lab)}))


if __name__=='__main__':main()
