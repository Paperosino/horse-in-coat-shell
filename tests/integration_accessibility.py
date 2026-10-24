#!/usr/bin/env python3
"""Inspect and activate real Qt Quick controls over a private AT-SPI bus."""
import json,os,shutil,subprocess,tempfile,time
from pathlib import Path
from integration_support import require_wayland_session
require_wayland_session();ROOT=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='hics-a11y-') as d:
 base=Path(d);shutil.copytree(ROOT/'shell',base/'shell',ignore=shutil.ignore_patterns('plugin','extras','__pycache__'))
 (base/'shell/shell.qml').write_text('''import QtQuick
import QtQuick.Layouts
import Quickshell
import qs.components
import qs.components.controls
import qs.modules.nexus.common
ShellRoot {
 FloatingWindow {title:"hics accessibility fixture";visible:true;implicitWidth:600;implicitHeight:400
  ColumnLayout {anchors.fill:parent;anchors.margins:20
   TextFieldRow {label:"Reader name";value:"Alice"}
   StepperRow {label:"Reader count";from:0;to:10;value:3}
   ToggleRow {text:"Enable reader alerts";checked:false}
   IconTextButton {text:"Confirm reader action";icon:"check";onClicked:console.log("ACCESSIBLE_ACTION_OK")}
  }
 }
}''')
 (base/'compositor.lua').write_text('hl.monitor({output="WAYLAND-1",mode="800x600@60",position="0x0",scale=1})\n')
 env=dict(os.environ,AQ_BACKEND='wayland',XDG_CONFIG_HOME=str(base/'config'),XDG_STATE_HOME=str(base/'state'),XDG_DATA_HOME=str(base/'data'),XDG_CACHE_HOME=str(base/'cache'));env.pop('HYPRLAND_INSTANCE_SIGNATURE',None)
 compositor=None
 try:
  with (base/'compositor.log').open('w') as log:compositor=subprocess.Popen(['Hyprland','--config',str(base/'compositor.lua')],env=env,stdout=log,stderr=subprocess.STDOUT)
  instance=None
  for _ in range(80):
   instance=next((i for i in json.loads(subprocess.check_output(['hyprctl','instances','-j'])) if i['pid']==compositor.pid),None)
   if instance:break
   time.sleep(.1)
  assert instance,'No nested compositor'
  env.update(WAYLAND_DISPLAY=instance['wl_socket'],HYPRLAND_INSTANCE_SIGNATURE=instance['instance'],QT_QPA_PLATFORM='wayland',QT_LINUX_ACCESSIBILITY_ALWAYS_ON='1',QT_ACCESSIBILITY='1',GSETTINGS_BACKEND='keyfile',QML_IMPORT_PATH=str(ROOT/'build/qml'),QML2_IMPORT_PATH=str(ROOT/'build/qml'))
  runner=base/'runner.py'
  runner.write_text('''import os,subprocess,time,sys
from pathlib import Path
import gi
gi.require_version("Atspi","2.0")
from gi.repository import Gio,GLib,Atspi
bus=Gio.bus_get_sync(Gio.BusType.SESSION,None)
for key in ("IsEnabled",):
 bus.call_sync("org.a11y.Bus","/org/a11y/bus","org.freedesktop.DBus.Properties","Set",GLib.Variant("(ssv)",("org.a11y.Status",key,GLib.Variant("b",True))),None,Gio.DBusCallFlags.NONE,5000,None)
address=bus.call_sync("org.a11y.Bus","/org/a11y/bus","org.a11y.Bus","GetAddress",None,None,Gio.DBusCallFlags.NONE,5000,None).unpack()[0]
os.environ["AT_SPI_BUS_ADDRESS"]=address
registry=subprocess.Popen(["/usr/lib/at-spi2-registryd"],env=dict(os.environ,DBUS_SESSION_BUS_ADDRESS=address))
time.sleep(.4)
speech=Gio.Settings.new_with_path("org.gnome.Orca.Speech","/org/gnome/orca/default/speech/")
speech.set_boolean("enable",False);Gio.Settings.sync()
reader_log=Path(sys.argv[2]+".orca").open('w')
reader=subprocess.Popen(["orca"],stdout=reader_log,stderr=subprocess.STDOUT)
log=Path(sys.argv[2]);f=log.open('w')
process=subprocess.Popen(["/usr/share/hics/qs/bin/hics-qs","-p",sys.argv[1]],stdout=f,stderr=subprocess.STDOUT)
def walk(node,depth=0):
 if depth>20:return []
 result=[node]
 for i in range(node.get_child_count()):
  try:result+=walk(node.get_child_at_index(i),depth+1)
  except Exception:pass
 return result
try:
 nodes=[]
 for _ in range(80):
  nodes=walk(Atspi.get_desktop(0));names=[n.get_name() for n in nodes]
  if 'Confirm reader action' in names:break
  if process.poll() is not None:raise RuntimeError(log.read_text())
  while GLib.MainContext.default().pending():GLib.MainContext.default().iteration(False)
  time.sleep(.1)
 names=[n.get_name() for n in nodes]
 for name in ('Reader name','Reader count','Enable reader alerts','Confirm reader action'):
  assert name in names,(name,names,log.read_text())
 button=next(n for n in nodes if n.get_name()=='Confirm reader action' and n.get_action_iface())
 action=button.get_action_iface();assert action.get_n_actions()>0
 assert action.do_action(0)
 for _ in range(30):
  if 'ACCESSIBLE_ACTION_OK' in log.read_text():break
  time.sleep(.1)
 assert 'ACCESSIBLE_ACTION_OK' in log.read_text(),log.read_text()
 assert reader.poll() is None,Path(sys.argv[2]+".orca").read_text()
 print('PASS: Orca remains running; AT-SPI names, editable fields, spinbox, toggle and button action')
finally:process.terminate();process.wait(timeout=5);reader.terminate();reader.wait(timeout=5);reader_log.close();registry.terminate();registry.wait(timeout=5);f.close()
''')
  run=subprocess.run(['dbus-run-session','--','python3',str(runner),str(base/'shell'),str(base/'shell.log')],env=env,capture_output=True,text=True,timeout=35)
  assert run.returncode==0,run.stdout+run.stderr
  print(run.stdout.strip())
 finally:
  if compositor:compositor.terminate();compositor.wait(timeout=5)
