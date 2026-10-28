#!/usr/bin/env python3
"""Build pinned Qt fixes into an immutable overlay for the bundled HICS runtime.

Never modifies system Qt or an existing overlay. Qt/QS module ABI and actual
portal/input/audio/video behavior still require the runtime regression gates.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tarfile
import tempfile
import urllib.request

ROOT=Path(__file__).resolve().parents[1]
VERSION='6.12.0'
SOURCES={
 'qtbase':('https://github.com/qt/qtbase/archive/refs/tags/v6.12.0.tar.gz','dff6570582c272cbe744d2e460700318262af505460f4215276459970ae31b46'),
 'qtdeclarative':('https://github.com/qt/qtdeclarative/archive/refs/tags/v6.12.0.tar.gz','0b71aa358703de8217177dbb620c86af9e9804482e607bb2cadbf116a65bd9c6'),
 'qtmultimedia':('https://github.com/qt/qtmultimedia/archive/refs/tags/v6.12.0.tar.gz','896543478b9dcdc1811e2960f74d926572cf5d97ce9ad7a53b6ea335cafe8561'),
 'renderdoc':('https://raw.githubusercontent.com/baldurk/renderdoc/v1.43/renderdoc/api/app/renderdoc_app.h','b7005e7dc34c3635046868bbd76d81b9b055aede0f56daa0bd39fedee0639ffb'),
}
PATCHES={'qtbase':['qtbase-6.12.0-portal-registration.patch','qtbase-6.12.0-text-input-focus.patch',
    'qtbase-6.12.0-maximized-decoration-geometry.patch','qtbase-6.12.0-lazy-wayland-decorations.patch',
    'qtbase-6.12.0-egl-context-adoption.patch'],
 'qtmultimedia':['qtmultimedia-6.12.0-lazy-hw-diagnostics.patch'],
 'qtdeclarative':['qtdeclarative-6.12.0-shadow-ownership.patch']}

def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()

def fetch(path,url,digest):
    if not path.exists():
        with tempfile.NamedTemporaryFile(dir=path.parent,delete=False) as stream:
            temporary=Path(stream.name)
            try:
                with urllib.request.urlopen(url,timeout=90) as reply:shutil.copyfileobj(reply,stream)
                stream.close()
                if sha(temporary)!=digest:raise RuntimeError('Source checksum mismatch: '+url)
                temporary.rename(path)
            finally:temporary.unlink(missing_ok=True)
    if sha(path)!=digest:raise RuntimeError('Cached source checksum mismatch: '+str(path))

def run(work,name,argv):
    with (work/(name+'.log')).open('w') as log:
        result=subprocess.run(argv,stdout=log,stderr=subprocess.STDOUT)
    if result.returncode:raise RuntimeError(name+' failed; inspect '+str(work/(name+'.log')))

def fields(path):
    return dict(re.findall(r'#define (QT_FEATURE_\w+) (-?\d+)',path.read_text()))

def header(headers,module,private=False):
    name=module.lower()+'-config'+('_p' if private else '')+'.h'
    return headers/module/VERSION/module/'private'/name if private else headers/module/name

def header_digest(directory):
    digest=hashlib.sha256()
    for path in sorted(directory.rglob('*.h')):
        digest.update(str(path.relative_to(directory)).encode()+b'\0')
        digest.update(path.read_bytes())
    return digest.hexdigest()

def apply_source_patch(source, patch):
    # --force disables GNU patch's auto-reversal guess, including during -R
    # dry-runs. Otherwise an unapplied patch can be mistaken for an applied one.
    command=['patch','--force','--batch','--fuzz=0','-p1','-i',str(patch)]
    reverse=subprocess.run([*command,'--reverse','--dry-run'],cwd=source,capture_output=True)
    if reverse.returncode:
        subprocess.run([*command,'--forward','--dry-run'],cwd=source,check=True,capture_output=True)
        subprocess.run([*command,'--forward'],cwd=source,check=True,capture_output=True)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--work',type=Path,required=True)
    p.add_argument('--stage',type=Path,required=True)
    p.add_argument('--jobs',type=int,default=2)
    a=p.parse_args();work=a.work.resolve();stage=a.stage.resolve()
    if not 1<=a.jobs<=16:p.error('Use 1..16 build jobs')
    version=subprocess.check_output(['qmake6','-query','QT_VERSION'],text=True).strip()
    if version!=VERSION:raise SystemExit('Qt runtime patches require audited Qt '+VERSION+', found '+version)
    headers=Path(subprocess.check_output(['qmake6','-query','QT_INSTALL_HEADERS'],text=True).strip())
    patch_hashes={name:sha(ROOT/'distribution/patches'/name) for names in PATCHES.values() for name in names}
    fingerprint={'quickEffectsBuild':sha(ROOT/'distribution/qtquickeffects/CMakeLists.txt'),'builder':sha(__file__),'patches':patch_hashes,'qtVersion':version,
        'headers':{module:header_digest(headers/module) for module in ('QtCore','QtGui','QtOpenGL','QtWaylandClient','QtMultimedia','QtQuickEffects','QtQml','QtQuick')}}
    # Ninja creates the output parent before invoking this command. Only an
    # empty placeholder may be removed; populated overlays stay immutable.
    if stage.is_dir() and not any(stage.iterdir()):
        stage.rmdir()
    if stage.exists():
        metadata=json.loads((stage/'hics-qt-patches.json').read_text())
        if metadata.get('fingerprint')!=fingerprint:raise SystemExit('Existing overlay is immutable; choose a new stage path')
        for name,digest in metadata['files'].items():
            if sha(stage/name)!=digest:raise SystemExit('Existing overlay checksum mismatch: '+name)
        for name,target in metadata['symlinks'].items():
            if not (stage/name).is_symlink() or os.readlink(stage/name)!=target:raise SystemExit('Existing overlay alias mismatch: '+name)
        print(stage);return
    work.mkdir(parents=True,exist_ok=True)
    for module in ('qtbase','qtmultimedia','qtdeclarative'):
        archive=work/(module+'-v'+VERSION+'.tar.gz');fetch(archive,*SOURCES[module])
        source=work/(module+'-'+VERSION)
        if not source.exists():
            with tarfile.open(archive) as bundle:bundle.extractall(work,filter='data')
        for name in PATCHES[module]:
            patch=ROOT/'distribution/patches'/name
            apply_source_patch(source, patch)
    renderdoc=work/'deps/renderdoc';renderdoc.mkdir(parents=True,exist_ok=True)
    fetch(renderdoc/'renderdoc_app.h',*SOURCES['renderdoc'])
    expected_core=fields(header(headers,'QtCore',True));expected_gui=fields(header(headers,'QtGui',True))
    def enabled(values,name):return 'ON' if values['QT_FEATURE_'+name]=='1' else 'OFF'
    base=work/'build-qtbase';media=work/'build-qtmultimedia'
    options=['-DQT_BUILD_TESTS=OFF','-DQT_BUILD_EXAMPLES=OFF','-DCMAKE_BUILD_TYPE=Release',
        '-DCMAKE_BUILD_WITH_INSTALL_RPATH=ON','-DINSTALL_PLUGINSDIR=lib/qt6/plugins']
    run(work,'hics-qtbase-configure',['cmake','-S',str(work/('qtbase-'+VERSION)),'-B',str(base),'-GNinja',
        '-DCMAKE_INSTALL_PREFIX='+str(work/'install'),*options,'-DFEATURE_system_zlib=ON','-DFEATURE_system_freetype=ON',
        '-DFEATURE_system_harfbuzz=ON','-DFEATURE_system_pcre2=ON','-DFEATURE_system_png=ON','-DFEATURE_system_jpeg=ON',
        '-DFEATURE_system_textmarkdownreader=OFF', # Match Qt's bundled md4c flags, not incompatible system headers.
        '-DFEATURE_journald='+enabled(expected_core,'journald'),'-DFEATURE_mimetype_database='+enabled(expected_core,'mimetype_database'),
        '-DINPUT_openssl=linked','-DFEATURE_openssl_linked=ON','-DFEATURE_openssl_hash='+enabled(expected_core,'openssl_hash'),
        '-DFEATURE_graphicsframecapture='+enabled(expected_gui,'graphicsframecapture'),'-DRenderDoc_INCLUDE_DIR='+str(renderdoc),
        '-DFEATURE_system_xcb_xinput='+enabled(expected_gui,'system_xcb_xinput')])
    run(work,'hics-qtbase-build',['cmake','--build',str(base),'--target','Gui','WaylandClient','QOffscreenIntegrationPlugin','QWaylandIntegrationPlugin','QWaylandEglClientBufferPlugin','-j'+str(a.jobs)])
    comparison={}
    for module,sub in [('QtCore','corelib'),('QtGui','gui'),('QtOpenGL','opengl'),('QtWaylandClient','plugins/platforms/wayland')]:
        for private in (False,True):
            installed=header(headers,module,private);name=installed.name;built=base/'src'/sub/name
            if not installed.exists() or not built.exists():continue
            original,current=fields(installed),fields(built)
            delta={key:[original.get(key),current.get(key)] for key in original.keys()|current.keys() if original.get(key)!=current.get(key)}
            allowed={'QT_FEATURE_system_textmarkdownreader'} if module=='QtGui' and not private else set()
            if set(delta)-allowed:raise RuntimeError('Unaccepted Qt feature changes: '+str(delta))
            comparison[module+('_private' if private else '')]=delta
    run(work,'hics-qtmultimedia-configure',['cmake','-S',str(work/('qtmultimedia-'+VERSION)),'-B',str(media),'-GNinja',
        '-DCMAKE_INSTALL_PREFIX='+str(work/'install-multimedia'),*options])
    run(work,'hics-qtmultimedia-build',['cmake','--build',str(media),'--target','QFFmpegMediaPlugin','-j'+str(a.jobs)])
    effects=work/'build-quickeffects'
    run(work,'hics-quickeffects-configure',['cmake','-S',str(ROOT/'distribution/qtquickeffects'),'-B',str(effects),'-GNinja',
        '-DHICS_QT_DECLARATIVE_SOURCE='+str(work/('qtdeclarative-'+VERSION)),
        '-DCMAKE_INSTALL_PREFIX='+str(work/'install-effects'),*options])
    run(work,'hics-quickeffects-build',['cmake','--build',str(effects),'--target','QuickEffects','effectsplugin','-j'+str(a.jobs)])
    stage.parent.mkdir(parents=True,exist_ok=True)
    temporary=Path(tempfile.mkdtemp(prefix='.hics-qt-stage-',dir=stage.parent))
    try:
        (temporary/'lib').mkdir()
        for library in ('Core','DBus','Gui','WaylandClient'):
            files=list((base/'lib').glob('libQt6'+library+'.so*'))
            if not files:raise RuntimeError('Missing rebuilt Qt library: '+library)
            for file in files:shutil.copy2(file,temporary/'lib'/file.name,follow_symlinks=False)
        for file in (effects/'lib').glob('libQt6QuickEffects.so*'):
            shutil.copy2(file,temporary/'lib'/file.name,follow_symlinks=False)
        if not (temporary/'lib/libQt6QuickEffects.so.6').is_file():
            raise RuntimeError('Missing rebuilt Qt QuickEffects library')
        for name,source in [('platforms/libqoffscreen.so',base/'lib/qt6/plugins/platforms/libqoffscreen.so'),
                            ('platforms/libqwayland.so',base/'lib/qt6/plugins/platforms/libqwayland.so'),
                            ('wayland-graphics-integration-client/libqt-plugin-wayland-egl.so',base/'lib/qt6/plugins/wayland-graphics-integration-client/libqt-plugin-wayland-egl.so'),
                            ('multimedia/libffmpegmediaplugin.so',media/'lib/qt6/plugins/multimedia/libffmpegmediaplugin.so')]:
            destination=temporary/'plugins'/name;destination.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,destination)
        (temporary/'lib/qt6').mkdir();(temporary/'lib/qt6/plugins').symlink_to('../../plugins',target_is_directory=True)
        licenses=temporary/'licenses';licenses.mkdir()
        shutil.copy2(work/('qtbase-'+VERSION)/'src/3rdparty/md4c/LICENSE.md',licenses/'md4c.txt')
        shutil.copy2(renderdoc/'renderdoc_app.h',licenses/'renderdoc-header.txt')
        shutil.copy2(work/('qtdeclarative-'+VERSION)/'LICENSES/LGPL-3.0-only.txt',licenses/'qtdeclarative-LGPL-3.0-only.txt')
        for path in temporary.rglob('*.so*'):
            if path.is_file() and not path.is_symlink():
                dynamic=subprocess.check_output(['readelf','-d',str(path)],text=True)
                if any(str(work) in line for line in dynamic.splitlines() if 'RPATH' in line or 'RUNPATH' in line):
                    raise RuntimeError('Nonrelocatable Qt library: '+str(path))
        metadata={'qtVersion':VERSION,'fingerprint':fingerprint,'patches':patch_hashes,'sources':SOURCES,'features':comparison,
            'scope':'QtCore/Gui/DBus/WaylandClient/QuickEffects and selected plugins; original Multimedia/Quick/Qml libraries and declarative plugins are retained',
            'symlinks':{str(path.relative_to(temporary)):os.readlink(path) for path in temporary.rglob('*') if path.is_symlink()},
            'files':{str(path.relative_to(temporary)):sha(path) for path in temporary.rglob('*') if path.is_file() and not path.is_symlink()}}
        (temporary/'hics-qt-patches.json').write_text(json.dumps(metadata,indent=2)+'\n')
        temporary.rename(stage)
    finally:
        if temporary.exists():shutil.rmtree(temporary)
    print(stage)

if __name__=='__main__':main()
