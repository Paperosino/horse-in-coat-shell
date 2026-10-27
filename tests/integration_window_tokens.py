#!/usr/bin/env python3
"""A layer window and its content must share the monitor's sizing policy."""
import json,os,shutil,subprocess,tempfile,time
from pathlib import Path
from integration_support import require_wayland_session, snapshot_qml_runtime, run_snapshot_qml
require_wayland_session()
ROOT=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='hics-window-tokens-') as directory:
 base=Path(directory);entry=base/'shell';entry.mkdir()
 shutil.copy2(ROOT/'shell/components/containers/StyledWindow.qml',entry/'StyledWindow.qml')
 lua=base/'compositor.lua';lua.write_text('hl.monitor({output="",mode="preferred",position="auto",scale=1})\n')
 env=dict(os.environ,AQ_BACKEND='wayland',XDG_CONFIG_HOME=str(base/'config'),XDG_STATE_HOME=str(base/'state'),XDG_DATA_HOME=str(base/'data'),XDG_CACHE_HOME=str(base/'cache'))
 env.pop('HYPRLAND_INSTANCE_SIGNATURE',None);compositor=None
 try:
  with (base/'compositor.log').open('w') as log:compositor=subprocess.Popen(['Hyprland','--config',str(lua)],env=env,stdout=log,stderr=subprocess.STDOUT)
  instance=None
  for _ in range(80):
   instance=next((i for i in json.loads(subprocess.check_output(['hyprctl','instances','-j'])) if i['pid']==compositor.pid),None)
   if instance:break
   time.sleep(.1)
  assert instance,'No nested compositor'
  monitors=json.loads(subprocess.check_output(['hyprctl','-i',instance['instance'],'monitors','-j']))
  cfg=base/'config/hics';cfg.mkdir(parents=True)
  (cfg/'shell.json').write_text('{"appearance":{"scale":1}}')
  specific=cfg/'monitors'/monitors[0]['name'];specific.mkdir(parents=True)
  (specific/'shell.json').write_text('{"appearance":{"scale":1.5,"padding":{"scale":2}}}')
  (entry/'shell.qml').write_text('''import QtQuick
import Quickshell
import Hyprstack.Config
ShellRoot {
 StyledWindow {
  id:win;name:"window-token-fixture";screen:Quickshell.screens[0];visible:true
  implicitWidth:300+Tokens.padding.large*2;implicitHeight:160
  property real directPadding:Tokens.padding.large
 }
 Timer {interval:700;running:true;onTriggered:{
  const expected=GlobalConfig.forScreen(win.screen.name).appearance.padding.large;
  const result={screen:win.screen.name,rootScreen:win.Tokens.screen,contentScreen:win.contentItem.Tokens.screen,rootPadding:win.directPadding,contentPadding:win.contentItem.Tokens.padding.large,expected:expected,globalPadding:GlobalConfig.appearance.padding.large};
  if(result.rootScreen!==result.screen||result.contentScreen!==result.screen||result.rootPadding!==expected||result.contentPadding!==expected||expected===result.globalPadding){console.error("WINDOW_TOKENS_FAILED",JSON.stringify(result));Qt.quit();return;}
  console.log("WINDOW_TOKENS_OK",JSON.stringify(result));Qt.quit();
 }}
}''')
  env.update(WAYLAND_DISPLAY=instance['wl_socket'],HYPRLAND_INSTANCE_SIGNATURE=instance['instance'],QT_QPA_PLATFORM='wayland')
  env.update(snapshot_qml_runtime(ROOT,base))
  result=run_snapshot_qml(['/usr/share/hics/qs/bin/hics-qs','--path',str(entry)],env,ROOT/'build',15)
  output=result.stdout+result.stderr;Path('/tmp/hics-window-tokens.log').write_text(output)
  assert result.returncode==0 and 'WINDOW_TOKENS_OK' in output and 'WINDOW_TOKENS_FAILED' not in output,output[-5000:]
  print('PASS: layer-window sizing and content share the actual monitor padding/scale instead of global fallback')
 finally:
  if compositor and compositor.poll() is None:
   compositor.terminate()
   try:compositor.wait(timeout=5)
   except subprocess.TimeoutExpired:compositor.kill();compositor.wait()
