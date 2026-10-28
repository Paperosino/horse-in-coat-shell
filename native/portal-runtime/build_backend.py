#!/usr/bin/env python3
"""Build the pinned patched Hyprland portal without replacing system files."""
import argparse
import hashlib
from pathlib import Path
import shutil
import subprocess
import tarfile
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
SOURCES = {
    'xdph': ('https://codeload.github.com/hyprwm/xdg-desktop-portal-hyprland/tar.gz/refs/tags/v1.4.1', '3652c14f63a9666acea2c841e196782dbc0f74ea5b4783622dd04a32f08b709f'),
    'protocols': ('https://codeload.github.com/hyprwm/hyprland-protocols/tar.gz/bd153e76f751f150a09328dbdeb5e4fab9d23622', 'f31112800ec83ec529d0d35699a3d20fa0ed3cbb97d344146340815fec5ac055'),
    'scanner': ('https://codeload.github.com/hyprwm/hyprwayland-scanner/tar.gz/refs/tags/v0.4.6', '05f55fd1a20d8ca81b5030980fdb7c87147749230145bdb3745af2741d617f5c'),
}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work', required=True, type=Path)
    parser.add_argument('--jobs', type=int, default=2)
    args = parser.parse_args()
    if not 1 <= args.jobs <= 32:
        parser.error('jobs must be between 1 and 32')
    work = args.work.resolve()
    work.mkdir(parents=True, exist_ok=True)
    if any(work.iterdir()):
        parser.error('Work directory must be empty')
    for name, (url, expected) in SOURCES.items():
        archive = work/(name+'.tar.gz')
        with urllib.request.urlopen(url, timeout=90) as response, archive.open('wb') as out:
            shutil.copyfileobj(response, out)
        with archive.open('rb') as stream:
            digest = hashlib.file_digest(stream,'sha256').hexdigest()
        if digest != expected:
            raise ValueError('Source checksum mismatch: '+name)
        target = work/(name+'-extract')
        target.mkdir()
        with tarfile.open(archive) as bundle:
            bundle.extractall(target, filter='data')
        children = list(target.iterdir())
        if len(children)!=1 or not children[0].is_dir():
            raise ValueError('Unexpected archive layout: '+name)
        children[0].rename(work/name)
    source = work/'xdph'
    protocols = source/'subprojects/hyprland-protocols'
    if protocols.exists():
        protocols.rmdir()  # Refuse to overwrite a nonempty upstream directory.
    shutil.move(str(work/'protocols'),str(protocols))
    with (ROOT/'native/portal-runtime/xdph-v1.4.1-experimental.patch').open('rb') as patch:
        subprocess.run(['patch','--force','--fuzz=0','-p1'],cwd=source,stdin=patch,check=True)
    prefix=work/'deps'
    subprocess.run(['cmake','-S',str(work/'scanner'),'-B',str(work/'scanner-build'),'-G','Ninja',
                    '-DCMAKE_BUILD_TYPE=Release','-DCMAKE_INSTALL_PREFIX='+str(prefix)],check=True)
    subprocess.run(['cmake','--build',str(work/'scanner-build'),'-j',str(args.jobs)],check=True)
    subprocess.run(['cmake','--install',str(work/'scanner-build')],check=True)
    import os
    env=dict(os.environ,PATH=str(prefix/'bin')+':'+os.environ.get('PATH',''),
             PKG_CONFIG_PATH=str(prefix/'lib/pkgconfig')+(':'+os.environ['PKG_CONFIG_PATH'] if os.environ.get('PKG_CONFIG_PATH') else ''))
    subprocess.run(['cmake','-S',str(source),'-B',str(work/'build'),'-G','Ninja',
                    '-DCMAKE_BUILD_TYPE=Release','-DSYSTEMD_SERVICES=OFF',
                    '-DHICS_PORTAL_RUNTIME_DIR='+str(ROOT/'native/portal-runtime')],env=env,check=True)
    subprocess.run(['cmake','--build',str(work/'build'),'--target','xdg-desktop-portal-hyprland','-j',str(args.jobs)],env=env,check=True)
    print('Built portal backend:',work/'build/xdg-desktop-portal-hyprland')

if __name__=='__main__':
    main()
