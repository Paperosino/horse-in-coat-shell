#!/usr/bin/env python3
"""A running shell resolves Flatpak icons installed, removed and reinstalled later."""
import json, os, shutil, subprocess, tempfile, time
from pathlib import Path
from integration_support import require_wayland_session, snapshot_qml_runtime
require_wayland_session()
ROOT=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='hics-flatpak-icons-') as directory:
    base=Path(directory); home=base/'home'; exports=home/'.local/share/flatpak/exports/share'
    icon_dir=exports/'icons/hicolor/scalable/apps';icon_dir.mkdir(parents=True)
    (exports/'applications').mkdir(parents=True);(base/'data').mkdir();(base/'system').mkdir()
    (exports/'icons/hicolor/index.theme').write_text('[Icon Theme]\nName=Hicolor\nDirectories=scalable/apps\n[scalable/apps]\nSize=48\nType=Scalable\nMinSize=1\nMaxSize=512\nContext=Applications\n')
    ui=base/'ui';ui.mkdir()
    for item in (ROOT/'shell').iterdir():
        if item.name != 'shell.qml': (ui/item.name).symlink_to(item,target_is_directory=item.is_dir())
    status=base/'status.json'
    (ui/'shell.qml').write_text('''//@ pragma IconTheme hicolor
import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Widgets
import Hyprstack.Services
import qs.utils
ShellRoot {
 FileView {id:out;path:STATUS;printErrors:false}
 IconImage {id:icon;implicitSize:48;source:Icons.themeIcon("org.hics.LateFlatpak", "image-missing");backer.cache:false}
 Timer {interval:100;repeat:true;running:true;onTriggered:{
  const entry=ApplicationCatalogue.byId("org.hics.LateFlatpak");
  out.setText(JSON.stringify({found:!!entry,match:ApplicationCatalogue.heuristicLookup("late-flatpak")?.id??"",revision:ApplicationCatalogue.iconRevision,
    available:!!Quickshell.iconPath("org.hics.LateFlatpak",true),source:String(icon.source),status:icon.status}));
 }}
}'''.replace('STATUS',json.dumps(str(status))))
    env=dict(os.environ,HOME=str(home),XDG_CONFIG_HOME=str(base/'config'),XDG_DATA_HOME=str(base/'data'),XDG_DATA_DIRS=str(base/'system'),XDG_CACHE_HOME=str(base/'cache'),XDG_STATE_HOME=str(base/'state'))
    if os.environ.get('HICS_TEST_INSTALLED_RUNTIME') == '1':
        env.update(QML_IMPORT_PATH='/usr/share/hics/qml',QML2_IMPORT_PATH='/usr/share/hics/qml',LD_LIBRARY_PATH='/usr/share/hics/qs/lib')
    else:
        env.update(snapshot_qml_runtime(ROOT,base/'runtime-snapshot'))
    config=base/'bus.conf';config.write_text('<busconfig><type>session</type><listen>unix:tmpdir='+str(base)+'</listen><policy context="default"><allow send_destination="*"/><allow receive_sender="*"/><allow own="*"/></policy></busconfig>')
    bus=subprocess.Popen(['dbus-daemon','--nofork','--print-address=1','--config-file='+str(config)],stdout=subprocess.PIPE,text=True);env['DBUS_SESSION_BUS_ADDRESS']=bus.stdout.readline().strip()
    log=(base/'shell.log').open('w'); shell=subprocess.Popen(['/usr/share/hics/qs/bin/hics-qs','-p',str(ui)],env=env,stdout=log,stderr=subprocess.STDOUT)
    def state():
        try:return json.loads(status.read_text())
        except (FileNotFoundError,json.JSONDecodeError):return {}
    def wait(check,label):
        deadline=time.monotonic()+12
        while time.monotonic()<deadline:
            data=state()
            if check(data):return data
            if shell.poll() is not None:break
            time.sleep(.1)
        log.flush();raise AssertionError((label,state(),(base/'shell.log').read_text()[-3000:]))
    try:
        before=wait(lambda s:'available' in s,'initial shell state');assert not before['found'] and not before['available'],before
        # The exported desktop and icon are symlinks, as with real Flatpak.
        payload=base/'payload';payload.mkdir()
        (payload/'app.desktop').write_text('[Desktop Entry]\nType=Application\nName=Late Flatpak\nExec=/bin/true\nIcon=org.hics.LateFlatpak\nStartupWMClass=late-flatpak\n')
        (payload/'icon.svg').write_text('<svg xmlns="http://www.w3.org/2000/svg" width="48" height="48"><rect width="48" height="48" fill="#00ff00"/></svg>')
        (exports/'applications/org.hics.LateFlatpak.desktop').symlink_to(payload/'app.desktop')
        (icon_dir/'org.hics.LateFlatpak.svg').symlink_to(payload/'icon.svg')
        ready=wait(lambda s:s.get('found') and s.get('match')=='org.hics.LateFlatpak' and s.get('available') and s.get('status')==1,'late Flatpak icon')
        assert ready['revision']>before['revision'],(before,ready)
        assert ready['source'].startswith('image://icon/org.hics.LateFlatpak?fallback='),ready
        print('PASS: late Flatpak export appears, matches its window class and resolves its icon',flush=True)
        (icon_dir/'org.hics.LateFlatpak.svg').unlink()
        removed=wait(lambda s:s.get('revision',0)>ready['revision'] and not s.get('available'),'icon removal')
        (icon_dir/'org.hics.LateFlatpak.svg').symlink_to(payload/'icon.svg')
        wait(lambda s:s.get('revision',0)>removed['revision'] and s.get('available') and s.get('status')==1,'icon reinstall')
        print('PASS: running shell refreshes removed and reinstalled icon',flush=True)
    finally:
        for p in (shell,bus):
            if p.poll() is None:
                p.terminate()
                try:p.wait(timeout=5)
                except subprocess.TimeoutExpired:p.kill();p.wait()
        log.close()
