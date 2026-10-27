#!/usr/bin/env python3
"""Validate and overlay rebuilt Qt components in a package staging directory."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import tempfile

def sha(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()

def relative(name):
    path=PurePosixPath(name)
    if path.is_absolute() or '..' in path.parts or not path.parts:raise ValueError('Unsafe Qt manifest path')
    return Path(*path.parts)

def verify(root,metadata):
    if not isinstance(metadata,dict) or metadata.get('qtVersion')!='6.12.0' or not isinstance(metadata.get('files'),dict) or len(metadata['files'])>100 or not isinstance(metadata.get('symlinks',{}),dict) or len(metadata.get('symlinks',{}))>100:
        raise ValueError('Invalid Qt overlay manifest')
    for name,digest in metadata['files'].items():
        file=root/relative(name)
        if not file.resolve().is_relative_to(root.resolve()) or file.is_symlink() or sha(file)!=digest:
            raise ValueError('Qt overlay checksum mismatch: '+name)
    for name,target in metadata.get('symlinks',{}).items():
        file=root/relative(name)
        if not file.is_symlink() or os.readlink(file)!=target or not file.resolve().is_relative_to(root.resolve()):
            raise ValueError('Qt overlay alias mismatch: '+name)

def read(root):
    file=root/'hics-qt-patches.json'
    descriptor=os.open(file,os.O_RDONLY|os.O_CLOEXEC|os.O_NOFOLLOW|os.O_NONBLOCK)
    with os.fdopen(descriptor,'rb') as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):raise ValueError('Qt manifest must be a regular file')
        raw=stream.read(1024*1024+1)
    if len(raw)>1024*1024:raise ValueError('Qt manifest is too large')
    metadata=json.loads(raw);verify(root,metadata);return metadata

def destination(name):
    path=relative(name)
    if path.parts[0]=='plugins':return Path('lib/qt6')/path
    if path.parts[0]=='licenses':return Path('licenses/qt-patches')/Path(*path.parts[1:])
    if len(path.parts)==2 and path.parts[0]=='lib' and path.name.startswith('libQt6'):return path
    raise ValueError('Unexpected Qt overlay file')

def apply(source,root):
    metadata=read(source) # Validate every file before replacing anything.
    if not (root/'bin').is_dir() or not (root/'lib').is_dir():raise ValueError('A staged Qt/QS bundle is required')
    files={str(destination(name)):digest for name,digest in metadata['files'].items()}
    aliases={name:target for name,target in metadata.get('symlinks',{}).items() if name!='lib/qt6/plugins'}
    for name in aliases:
        if destination(name)!=relative(name):raise ValueError('Unexpected Qt library alias')
    for name in metadata['files']:
        target=root/destination(name);target.parent.mkdir(parents=True,exist_ok=True)
        fd,tmp=tempfile.mkstemp(prefix='.hics-qt-',dir=target.parent);os.close(fd)
        try:
            shutil.copy2(source/name,tmp);os.replace(tmp,target)
        finally:Path(tmp).unlink(missing_ok=True)
    for name,value in aliases.items():
        target=root/relative(name)
        fd,tmp=tempfile.mkstemp(prefix='.hics-qt-',dir=target.parent);os.close(fd);os.unlink(tmp)
        try:os.symlink(value,tmp);os.replace(tmp,target)
        finally:Path(tmp).unlink(missing_ok=True)
    metadata=dict(metadata,files=files,symlinks=aliases)
    (root/'hics-qt-patches.json').write_text(json.dumps(metadata,indent=2)+'\n')
    verify(root,metadata)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--overlay',type=Path)
    p.add_argument('--root',type=Path,required=True)
    a=p.parse_args()
    if a.overlay:apply(a.overlay,a.root)
    else:read(a.root)

if __name__=='__main__':main()
