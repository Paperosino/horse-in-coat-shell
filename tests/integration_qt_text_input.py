#!/usr/bin/env python3
"""Real Qt/Wayland text-input focus and typing on a private nested compositor.

--runtime selects the existing bundled qs; --qt-overlay optionally selects
rebuilt Qt libraries/plugins. Does not change host focus, keyboard or services.
"""
import argparse
import json
import os
from pathlib import Path
import select
import shlex
import shutil
import subprocess
import tempfile
import time
from integration_support import require_wayland_session

ROOT=Path(__file__).resolve().parents[1]
QML='''import QtQuick
import Quickshell
import Quickshell.Io
ShellRoot {
 id:root
 property var extraWindow:null
 Component {id:extraFactory;FloatingWindow {title:"HICS text input extra";visible:true;implicitWidth:400;implicitHeight:260
  property alias value:field.text
  function edit(){field.forceActiveFocus();}
  TextInput {id:field;width:300;height:80;focus:true}
 }}
 FloatingWindow { title:"HICS text input A";visible:true;implicitWidth:400;implicitHeight:260
  TextInput {id:a;width:300;height:80;text:"";focus:true}
 }
 FloatingWindow { title:"HICS text input B";visible:true;implicitWidth:400;implicitHeight:260
  TextInput {id:b;width:300;height:80;text:""}
  Rectangle {id:neutral;y:100;width:200;height:100;color:"#544363";focus:true}
 }
 IpcHandler {
  target:"textFixture"
  function select(name:string):void {
   if(name==="a")a.forceActiveFocus();
   else if(name==="b")b.forceActiveFocus();
   else if(name==="extra")root.extraWindow.edit();
   else neutral.forceActiveFocus();
  }
  function openExtra():void {root.extraWindow=extraFactory.createObject(root);}
  function closeExtra():void {const window=root.extraWindow;root.extraWindow=null;window.destroy();}
  function state():string {return JSON.stringify({a:a.text,b:b.text,af:a.activeFocus,bf:b.activeFocus,extra:root.extraWindow?.value??null});}
 }
}
'''

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime',required=True,type=Path)
    parser.add_argument('--qt-overlay',type=Path)
    parser.add_argument('--without-ime',action='store_true')
    parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--keyboard-binary',type=Path)
    parser.add_argument('--export-keyboard',type=Path)
    args=parser.parse_args()
    if args.output.exists():parser.error('Use a fresh evidence path')
    require_wayland_session()
    # Hyprland adds its long instance signature and socket filename below this
    # directory. Keep the AF_UNIX path below sun_path's limit independently of
    # TMPDIR; the descriptive evidence directory can remain separate.
    with tempfile.TemporaryDirectory(prefix='hics-qt-input-') as directory, \
         tempfile.TemporaryDirectory(prefix='hi-',dir='/tmp') as runtime_directory:
        base=Path(directory);runtime=Path(runtime_directory)
        entry=base/'shell.qml';entry.write_text(QML)
        config=base/'compositor.lua';config.write_text('hl.monitor({output="",mode="1280x800@60",position="auto",scale=1})\n')
        bus_config=base/'bus.conf';bus_config.write_text('<busconfig><type>session</type><listen>unix:tmpdir='+str(base)+'</listen><policy context="default"><allow send_destination="*"/><allow receive_sender="*"/><allow own="*"/></policy></busconfig>')
        bus=subprocess.Popen(['dbus-daemon','--nofork','--print-address=1','--config-file='+str(bus_config)],stdout=subprocess.PIPE,text=True)
        compositor=app=keyboard=ime=None
        try:
            assert select.select([bus.stdout],[],[],5)[0],'Private bus not ready'
            address=bus.stdout.readline().strip();assert address
            env=dict(os.environ,HOME=str(base/'home'),XDG_RUNTIME_DIR=str(runtime),
                XDG_CONFIG_HOME=str(base/'config'),XDG_DATA_HOME=str(base/'data'),
                XDG_STATE_HOME=str(base/'state'),XDG_CACHE_HOME=str(base/'cache'),
                DBUS_SESSION_BUS_ADDRESS=address,DBUS_SYSTEM_BUS_ADDRESS=address,
                PIPEWIRE_REMOTE='hics-input-absent',PULSE_SERVER='unix:'+str(base/'absent-audio'))
            env.pop('HYPRLAND_INSTANCE_SIGNATURE',None)
            parent=os.environ['WAYLAND_DISPLAY']
            if not parent.startswith('/'):parent=str(Path(os.environ['XDG_RUNTIME_DIR'])/parent)
            with (base/'compositor.log').open('w') as log:
                compositor=subprocess.Popen(['Hyprland','--config',str(config)],env=dict(env,WAYLAND_DISPLAY=parent,AQ_BACKEND='wayland'),stdout=log,stderr=subprocess.STDOUT)
            instance=None;deadline=time.monotonic()+15
            while time.monotonic()<deadline:
                assert compositor.poll() is None,(base/'compositor.log').read_text()[-3000:]
                raw=subprocess.check_output(['hyprctl','instances','-j'],env=env,text=True,timeout=5).strip()
                if not raw.startswith('['):
                    time.sleep(.1);continue
                rows=json.loads(raw)
                instance=next((row for row in rows if row['pid']==compositor.pid),None)
                if instance:break
                time.sleep(.1)
            assert instance,'Nested compositor not ready'
            env.update(WAYLAND_DISPLAY=instance['wl_socket'],HYPRLAND_INSTANCE_SIGNATURE=instance['instance'])
            # IPC is published before Aquamarine has configured its output.
            # Wait for real usable geometry before creating maximizable Qt windows.
            deadline=time.monotonic()+15
            monitors=[]
            while time.monotonic()<deadline:
                assert compositor.poll() is None,(base/'compositor.log').read_text()[-3000:]
                monitors=json.loads(subprocess.check_output(['hyprctl','-i',instance['instance'],'monitors','-j'],env=env,text=True,timeout=5))
                if any(m.get('width',0)>0 and m.get('height',0)>0 for m in monitors):break
                time.sleep(.1)
            else:raise AssertionError(('Nested compositor has no usable output',monitors))
            if not args.without_ime:
                profile=base/'config/fcitx5/profile';profile.parent.mkdir(parents=True)
                profile.write_text('[Groups/0]\nName=Default\nDefault Layout=us\nDefaultIM=keyboard-us\n[Groups/0/Items/0]\nName=keyboard-us\nLayout=\n[GroupOrder]\n0=Default\n')
                with (base/'ime.log').open('w') as log:
                    ime=subprocess.Popen(['fcitx5','-D','--disable=all','--enable=wayland,waylandim,keyboard,dbus,dbusfrontend'],env=dict(env,XDG_SESSION_TYPE='wayland'),stdout=log,stderr=subprocess.STDOUT)
                deadline=time.monotonic()+10
                while time.monotonic()<deadline:
                    assert ime.poll() is None,(base/'ime.log').read_text()[-3000:]
                    reply=subprocess.run(['gdbus','call','--address',address,'--dest','org.freedesktop.DBus','--object-path','/org/freedesktop/DBus','--method','org.freedesktop.DBus.NameHasOwner','org.fcitx.Fcitx5'],env=env,capture_output=True,text=True,timeout=2)
                    if reply.returncode==0 and reply.stdout.strip()=='(true,)':break
                    time.sleep(.1)
                else:raise AssertionError((base/'ime.log').read_text()[-3000:])
            def ctl(*arguments):
                return subprocess.check_output(['hyprctl','-i',instance['instance'],*arguments],env=env,text=True,timeout=5).strip()
            fixtures=ROOT/'tests/fixtures'
            for mode,target in [('client-header','virtual-keyboard.h'),('private-code','keyboard-protocol.c')]:
                subprocess.run(['wayland-scanner',mode,str(fixtures/'virtual-keyboard.xml'),str(base/target)],check=True,capture_output=True)
            source=base/'keyboard.c';source.write_text((fixtures/'virtual-keyboard-stream.c').read_text().replace('.layout="us"','.layout="us",.options="compose:ralt"'))
            if args.keyboard_binary:shutil.copy2(args.keyboard_binary,base/'keyboard')
            else:
                flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','wayland-client','xkbcommon'],text=True))
                subprocess.run(['cc',str(source),str(base/'keyboard-protocol.c'),'-I'+str(base),*flags,'-o',str(base/'keyboard')],check=True,capture_output=True)
            if args.export_keyboard:shutil.copy2(base/'keyboard',args.export_keyboard)
            keyboard=subprocess.Popen([str(base/'keyboard')],env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True)
            def ack():
                assert select.select([keyboard.stdout],[],[],5)[0],'Virtual keyboard did not respond'
                return keyboard.stdout.readline().strip()
            assert ack()=='ready'
            qt=dict(env,QT_QPA_PLATFORM='wayland',QT_QUICK_BACKEND='software',QT_IM_MODULE='wayland',QT_IM_MODULES='wayland',
                QT_WAYLAND_TEXT_INPUT_PROTOCOL='zwp_text_input_v3',WAYLAND_DEBUG='client',
                QML_IMPORT_PATH=str(args.runtime/'lib/qt6/qml'),QML2_IMPORT_PATH=str(args.runtime/'lib/qt6/qml'),
                QT_PLUGIN_PATH=str(args.runtime/'lib/qt6/plugins'),LD_LIBRARY_PATH=str(args.runtime/'lib'))
            if args.qt_overlay:
                qt['LD_LIBRARY_PATH']=str(args.qt_overlay/'lib')+':'+qt['LD_LIBRARY_PATH']
                qt['QT_PLUGIN_PATH']=str(args.qt_overlay/'plugins')+':'+qt['QT_PLUGIN_PATH']
            binary=args.runtime/'bin/hics-qs'
            with (base/'app.log').open('w') as log:
                app=subprocess.Popen([str(binary),'-p',str(entry)],env=qt,stdout=log,stderr=subprocess.STDOUT)
            deadline=time.monotonic()+15
            while time.monotonic()<deadline:
                assert app.poll() is None,(base/'app.log').read_text()[-4000:]
                clients=json.loads(ctl('clients','-j'))
                if len([c for c in clients if c.get('pid')==app.pid])==2:break
                time.sleep(.1)
            else:raise AssertionError(('Text input windows not mapped',{'appPid':app.pid,'clients':clients,'monitors':ctl('monitors','-j')}))
            mappings=Path('/proc')/str(app.pid)/'maps';loaded=mappings.read_text()
            required=args.qt_overlay or args.runtime
            for library in ('libQt6Gui.so','libQt6WaylandClient.so'):
                assert str(required/'lib'/library) in loaded, 'Expected selected Qt runtime: '+library
            forbidden=os.environ.get('HICS_QT_FORBID_MAPS')
            if forbidden:assert forbidden not in loaded,'Test maps a mutable Qt build'
            windows={c['title']:c for c in clients if c.get('pid')==app.pid}
            def focus(letter):
                address=windows['HICS text input '+letter]['address']
                ctl('eval','hl.dispatch(hl.dsp.focus({window=hl.get_window('+json.dumps('address:'+address)+')}))')
                assert json.loads(ctl('activewindow','-j'))['address']==address
            def ipc(*arguments):
                return subprocess.check_output([str(binary),'ipc','-p',str(entry),'call','textFixture',*arguments],env=qt,text=True,stderr=subprocess.PIPE,timeout=5).strip()
            def key(code):
                for state in (1,0):
                    keyboard.stdin.write(f'key {code} {state}\n');keyboard.stdin.flush();assert ack()=='ok'
            for _ in range(5):
                focus('A');ipc('select','a');time.sleep(.1);key(30)
                focus('B');ipc('select','neutral');time.sleep(.1)
                ipc('select','b');key(48);ipc('select','neutral')
            state=json.loads(ipc('state'));assert state['a']=='aaaaa' and state['b']=='bbbbb',state
            for _ in range(6):
                ipc('openExtra');deadline=time.monotonic()+5;extra=None
                while time.monotonic()<deadline:
                    extra=next((c for c in json.loads(ctl('clients','-j')) if c.get('pid')==app.pid and c['title']=='HICS text input extra'),None)
                    if extra:break
                    time.sleep(.05)
                assert extra,'Transient input window not mapped'
                ctl('eval','hl.dispatch(hl.dsp.focus({window=hl.get_window('+json.dumps('address:'+extra['address'])+')}))')
                ipc('select','extra');time.sleep(.1);key(46);time.sleep(.05)
                assert json.loads(ipc('state'))['extra']=='c'
                ipc('closeExtra');focus('A');ipc('select','a');time.sleep(.1);key(45)
            focus('A');ipc('select','a');time.sleep(.1)
            for code in (100,40,18):key(code)
            time.sleep(.1);composed=json.loads(ipc('state'))
            assert composed['a']=='aaaaa'+'x'*6+'é',composed
            output=(base/'app.log').read_text()
            assert 'new id zwp_text_input_v3' in output,'Text-input-v3 was not bound'
            if not args.without_ime:
                assert '.enable(' in output and '.disable(' in output,'Text-input-v3 was not exercised with IME'
            warnings=[line for line in output.splitlines() if 'Trying to disable' in line or 'Trying to enable' in line]
            report={'typed':state,'compose':composed,'textInputWarnings':warnings,'runtime':str(args.runtime),
                'overlay':str(args.qt_overlay) if args.qt_overlay else None,'cycles':5,'destroyFocusedWindows':6,'realFcitx':not args.without_ime}
            args.output.with_suffix('.log').write_text(output)
            args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
            assert not warnings,warnings
            print(json.dumps(report,ensure_ascii=False,indent=2))
        except BaseException:
            native_logs=sorted(runtime.glob('hypr/*/hyprland.log'))
            if native_logs:
                args.output.with_suffix('.hyprland.log').write_bytes(native_logs[-1].read_bytes())
            if (base/'app.log').exists():args.output.with_suffix('.log').write_bytes((base/'app.log').read_bytes())
            if (base/'compositor.log').exists():args.output.with_suffix('.compositor.log').write_bytes((base/'compositor.log').read_bytes())
            if (base/'ime.log').exists():args.output.with_suffix('.ime.log').write_bytes((base/'ime.log').read_bytes())
            raise
        finally:
            for process in (app,keyboard,ime,compositor,bus):
                if process and process.poll() is None:
                    process.terminate()
                    try:process.wait(timeout=5)
                    except subprocess.TimeoutExpired:process.kill();process.wait(timeout=5)
            if keyboard:
                keyboard.stdin.close();keyboard.stdout.close()
            bus.stdout.close()

if __name__=='__main__':main()
