#!/usr/bin/env python3
"""Observe the installed session manager on an isolated fake logind bus.

Never connects to the real system or session bus. A positive Terminate event
shows the old immediate-termination behavior; it is not a successful logout test.
"""
import argparse
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile
import time
from integration_support import require_wayland_session

ROOT = Path(__file__).resolve().parents[1]
MOCK = r'''
import dbus, dbus.service
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib
import os
DBusGMainLoop(set_as_default=True)
bus=dbus.bus.BusConnection(os.environ['DBUS_SYSTEM_BUS_ADDRESS'])
name=dbus.service.BusName('org.freedesktop.login1',bus)
class Manager(dbus.service.Object):
 @dbus.service.method('org.freedesktop.login1.Manager',in_signature='s',out_signature='o')
 def GetSession(self,value):return dbus.ObjectPath('/org/freedesktop/login1/session/test')
class Session(dbus.service.Object):
 @dbus.service.method('org.freedesktop.login1.Session')
 def Terminate(self):
  with open(os.environ['HICS_TEST_TRACE'],'a') as stream:stream.write('Terminate\n')
manager=Manager(bus,'/org/freedesktop/login1');session=Session(bus,'/org/freedesktop/login1/session/test')
print('ready',flush=True);GLib.MainLoop().run()
'''
PROBE = r'''
#include "sessionmanager.hpp"
#include <QCoreApplication>
#include <QTimer>
int main(int argc,char**argv) {
 QCoreApplication app(argc,argv);
 hyprstack::services::SessionManager manager;
 manager.logout();
 QTimer::singleShot(500,&app,&QCoreApplication::quit);
 return app.exec();
}
'''
WINDOW = r'''
#include <QApplication>
#include <QCloseEvent>
#include <QFile>
#include <QMainWindow>
class Editor : public QMainWindow {
 void closeEvent(QCloseEvent *event) override {
  QFile trace(qEnvironmentVariable("HICS_TEST_WINDOW_TRACE"));
  if (trace.open(QIODevice::Append)) trace.write("close-request\n");
  event->ignore(); // An editor with unsaved changes declines to close.
 }
};
int main(int argc,char**argv) {
 QApplication app(argc,argv); Editor window;
 window.setWindowTitle("HICS unsaved document fixture");window.resize(480,320);window.show();
 return app.exec();
}
'''

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',required=True,type=Path)
    p.add_argument('--library-dir',type=Path,default=Path('/usr/share/hics/qml/Hyprstack/lib'),help='Directory containing the session manager and its companion libraries')
    p.add_argument('--qt-lib-dir',type=Path,default=Path('/usr/share/hics/qs/lib'),help='Matching private Qt runtime libraries')
    p.add_argument('--nested-window',action='store_true',help='Observe an unsaved-window fixture in a nested compositor')
    args=p.parse_args()
    if args.output.exists():p.error('Use a fresh output file')
    if args.nested_window:require_wayland_session()
    with tempfile.TemporaryDirectory(prefix='hics-logout-audit-') as temporary:
        root=Path(temporary);library=root/'libs';library.mkdir()
        runtime=root/'run';runtime.mkdir(mode=0o700)
        for path in args.library_dir.glob('*.so*'):
            if path.is_file():shutil.copy2(path,library/path.name,follow_symlinks=True)
        if not (library/'libhyprstack-services.so').is_file():
            p.error('The selected library directory does not contain the services library')
        trace=root/'trace';source=root/'probe.cpp';source.write_text(PROBE)
        flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','Qt6Core','Qt6DBus','Qt6Qml'],text=True))
        subprocess.run(['c++','-std=c++20','-fPIC',str(source),'-I'+str(ROOT/'shell/plugin/src/Hyprstack/Services'),
                        '-L'+str(library),'-lhyprstack-services','-Wl,-rpath,'+str(library),*flags,'-o',str(root/'probe')],check=True)
        if args.nested_window:
            editor_source=root/'editor.cpp';editor_source.write_text(WINDOW)
            widgets=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','Qt6Widgets'],text=True))
            subprocess.run(['c++','-std=c++20','-fPIC',str(editor_source),*widgets,'-o',str(root/'editor')],check=True)
        bus_config=root/'bus.conf'
        bus_config.write_text('<busconfig><type>session</type><listen>unix:tmpdir='+str(root)+'</listen><policy context="default"><allow send_destination="*"/><allow receive_sender="*"/><allow own="*"/></policy></busconfig>')
        bus=subprocess.Popen(['dbus-daemon','--nofork','--print-address=1','--config-file='+str(bus_config)],stdout=subprocess.PIPE,text=True)
        mock=compositor=editor=None
        try:
            address=bus.stdout.readline().strip();assert address
            env=dict(os.environ,HOME=str(root),XDG_CONFIG_HOME=str(root/'config'),XDG_STATE_HOME=str(root/'state'),
                     XDG_DATA_HOME=str(root/'data'),XDG_CACHE_HOME=str(root/'cache'),
                     DBUS_SYSTEM_BUS_ADDRESS=address,DBUS_SESSION_BUS_ADDRESS=address,
                     XDG_RUNTIME_DIR=str(runtime),GSETTINGS_BACKEND='memory',PULSE_SERVER='unix:'+str(root/'no-pulse'),
                     HICS_TEST_TRACE=str(trace),LD_LIBRARY_PATH=str(library)+':'+str(args.qt_lib_dir.resolve()))
            mock=subprocess.Popen(['python3','-c',MOCK],env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
            assert mock.stdout.readline().strip()=='ready'
            if args.nested_window:
                config=root/'hyprland.lua';config.write_text('hl.monitor({output="WAYLAND-1",mode="800x600@60",position="0x0",scale=1})\n')
                display=os.environ['WAYLAND_DISPLAY']
                env['WAYLAND_DISPLAY']=display if display.startswith('/') else str(Path(os.environ['XDG_RUNTIME_DIR'])/display)
                env['AQ_BACKEND']='wayland';env.pop('HYPRLAND_INSTANCE_SIGNATURE',None)
                compositor_log=(root/'compositor.log').open('w')
                compositor_env=dict(env);compositor_env.pop('LD_LIBRARY_PATH',None)
                compositor=subprocess.Popen(['Hyprland','--config',str(config)],env=compositor_env,stdout=compositor_log,stderr=subprocess.STDOUT)
                deadline=time.monotonic()+20
                while True:
                    assert compositor.poll() is None, 'Nested compositor exited'
                    raw=subprocess.check_output(['hyprctl','instances','-j'],env=env,text=True,timeout=3)
                    try:instances=json.loads(raw)
                    except json.JSONDecodeError:instances=[]
                    instance=next((x for x in instances if x['pid']==compositor.pid),None)
                    if instance:
                        monitors=json.loads(subprocess.check_output(['hyprctl','-i',instance['instance'],'monitors','-j'],env=env,text=True,timeout=3))
                        if monitors:break
                    assert time.monotonic()<deadline,'Nested compositor output not ready'
                    time.sleep(.1)
                env['WAYLAND_DISPLAY']=instance['wl_socket']
                env['HYPRLAND_INSTANCE_SIGNATURE']=instance['instance']
                env['HICS_TEST_WINDOW_TRACE']=str(root/'window-trace')
                editor=subprocess.Popen([str(root/'editor')],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
                while True:
                    assert editor.poll() is None,'Unsaved-window fixture exited'
                    clients=json.loads(subprocess.check_output(['hyprctl','-i',instance['instance'],'clients','-j'],env=env,text=True,timeout=3))
                    window=next((x for x in clients if x.get('pid')==editor.pid and x.get('mapped')),None)
                    if window:break
                    assert time.monotonic()<deadline,'Unsaved-window fixture not mapped'
                    time.sleep(.1)
            result=subprocess.run([str(root/'probe')],env=env,capture_output=True,text=True,timeout=10)
            if result.returncode:raise RuntimeError(result.stderr)
            events=trace.read_text().splitlines() if trace.exists() else []
            report={'events':events,'directTerminateObserved':'Terminate' in events,
                    'scope':'installed SessionManager against isolated fake logind; no real windows or desktop sessions'}
            if args.nested_window:
                report['scope']='SessionManager against fake logind with a real unsaved-window fixture in nested Hyprland'
                report['windowMappedBeforeLogout']=True
                report['windowStillAlive']=editor.poll() is None
                window_trace=root/'window-trace'
                report['windowReceivedClose']=window_trace.exists() and 'close-request' in window_trace.read_text()
                # Positive control: the same fixture must observe a real close
                # request while remaining open after it rejects the request.
                selector='address:'+window['address']
                expression='local w=hl.get_window('+json.dumps(selector)+');hl.dispatch(hl.dsp.window.close({window=w}))'
                subprocess.run(['hyprctl','-i',instance['instance'],'eval',expression],env=env,check=True,capture_output=True,timeout=3)
                until=time.monotonic()+5
                while not window_trace.exists():
                    assert editor.poll() is None and time.monotonic()<until,'Close-event fixture did not respond'
                    time.sleep(.05)
                report['positiveControlCloseObserved']='close-request' in window_trace.read_text()
                report['positiveControlWindowStillAlive']=editor.poll() is None
                assert report['positiveControlCloseObserved'] and report['positiveControlWindowStillAlive']
            args.output.write_text(json.dumps(report,indent=2)+'\n')
            print(json.dumps(report,indent=2))
        finally:
            for process in (editor,compositor):
                if process and process.poll() is None:
                    process.terminate()
                    try:process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill();process.wait()
            if compositor:
                compositor_log.close()
            if mock:
                mock.terminate();mock.wait(timeout=5)
            bus.terminate();bus.wait(timeout=5)

if __name__=='__main__':main()
