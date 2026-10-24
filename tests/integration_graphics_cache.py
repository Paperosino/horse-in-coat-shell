#!/usr/bin/env python3
"""Real Quickshell panels write and reload distinct driver-local Qt caches."""
import json,os,shutil,subprocess,tempfile,time
from pathlib import Path
from integration_support import require_wayland_session
require_wayland_session()
ROOT=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='hics-graphics-cache-') as directory:
 base=Path(directory);shutil.copytree(ROOT/'shell',base/'shell',ignore=shutil.ignore_patterns('plugin','extras','__pycache__'))
 (base/'shell/shell.qml').write_text('''import QtQuick
import Quickshell
import Quickshell.Widgets
import QtQuick.Effects
import qs.components.containers
ShellRoot {
 Variants {model:["cache-probe-a","cache-probe-b"]
  StyledWindow {required property string modelData;name:modelData;implicitWidth:500;implicitHeight:110
   anchors.top:modelData.endsWith("a");anchors.bottom:!modelData.endsWith("a")
   Rectangle {anchors.fill:parent;gradient:Gradient {GradientStop {position:0;color:"#4455aa"}GradientStop {position:1;color:"#aa3366"}}}
   Row {anchors.centerIn:parent;Repeater {model:10;IconImage {implicitSize:42;source:Quickshell.iconPath(index%2?"folder":"text-x-generic",true)}}}
  }
 }
 Timer {interval:2500;running:true;onTriggered:Qt.quit()}
}''')
 (base/'test.lua').write_text('hl.monitor({output="WAYLAND-1",mode="1280x720@60",position="0x0",scale=1})\n')
 env=dict(os.environ,AQ_BACKEND='wayland',XDG_CONFIG_HOME=str(base/'config'),XDG_STATE_HOME=str(base/'state'),XDG_CACHE_HOME=str(base/'cache'),XDG_DATA_HOME=str(base/'data'))
 env.pop('HYPRLAND_INSTANCE_SIGNATURE',None)
 compositor=None
 try:
  with (base/'compositor.log').open('w') as log:compositor=subprocess.Popen(['Hyprland','--config',str(base/'test.lua')],env=env,stdout=log,stderr=subprocess.STDOUT)
  for _ in range(80):
   instance=next((i for i in json.loads(subprocess.check_output(['hyprctl','instances','-j'])) if i['pid']==compositor.pid),None)
   if instance:break
   time.sleep(.1)
  assert instance,'Nested compositor did not start'
  env.update(WAYLAND_DISPLAY=instance['wl_socket'],HYPRLAND_INSTANCE_SIGNATURE=instance['instance'],QML_IMPORT_PATH=str(ROOT/'build/qml'),QML2_IMPORT_PATH=str(ROOT/'build/qml'),QT_QPA_PLATFORM='wayland',QSG_INFO='1')
  for iteration in range(2):
   run=subprocess.run(['/usr/share/hics/qs/bin/hics-qs','-p',str(base/'shell')],env=env,capture_output=True,text=True,timeout=8)
   output=run.stdout+run.stderr;Path(f'/tmp/hics-graphics-cache-{iteration}.log').write_text(output)
   assert run.returncode==0 and 'Failed to load configuration' not in output,output[-5000:]
   assert not any(s in output for s in ('TypeError:','ReferenceError:','Binding loop','Cannot assign','Unable to assign')),output[-5000:]
   caches=list((base/'cache').rglob('hics-pipelines/*/*.qpc'))
   assert len(caches)==2 and all(c.stat().st_size>0 for c in caches),(caches,output[-6000:])
   if iteration:assert 'Attempting to seed pipeline cache' in output,output[-6000:]
  disabled=dict(env,QT_DISABLE_SHADER_DISK_CACHE='1',XDG_CACHE_HOME=str(base/'cache-disabled'))
  run=subprocess.run(['/usr/share/hics/qs/bin/hics-qs','-p',str(base/'shell')],env=disabled,capture_output=True,text=True,timeout=8)
  assert run.returncode==0 and not list((base/'cache-disabled').rglob('*.qpc')),(run.stdout+run.stderr)[-5000:]
  print('PASS: two real panels save and reload separate Qt pipeline caches; native Qt icon rendering retained')
 finally:
  if compositor and compositor.poll() is None:
   compositor.terminate()
   try:compositor.wait(timeout=5)
   except subprocess.TimeoutExpired:compositor.kill();compositor.wait()
