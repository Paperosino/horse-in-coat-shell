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
 shutil.copy2(ROOT/'shell/components/images/ProfileImage.qml',entry/'ProfileImage.qml')
 home=base/'home';home.mkdir()
 from PIL import Image
 Image.new('RGB',(20,20),'red').save(home/'.face',format='PNG')
 lua=base/'compositor.lua';lua.write_text('hl.monitor({output="",mode="preferred",position="auto",scale=1})\n')
 env=dict(os.environ,HOME=str(home),AQ_BACKEND='wayland',XDG_CONFIG_HOME=str(base/'config'),XDG_STATE_HOME=str(base/'state'),XDG_DATA_HOME=str(base/'data'),XDG_CACHE_HOME=str(base/'cache'))
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
  navigation=(ROOT/'shell/modules/nexus/navpane/NavLocations.qml').read_text()
  tooltip='ToolTip {'+navigation.split('ToolTip {',1)[1].split('\n                }',1)[0]+'\n}'
  # Keep the production popup's Tokens/Config bindings; colour/font services
  # are independent of this monitor propagation test and stay isolated.
  tooltip=tooltip.replace('StyledRect','Rectangle').replace('StyledText','Text')
  tooltip=tooltip.replace('Colours.palette.m3inverseSurface','"#222222"').replace('Colours.palette.m3inverseOnSurface','"#eeeeee"')
  (entry/'shell.qml').write_text('''import QtQuick
import Quickshell
import QtQuick.Controls
import Hyprstack.Config
ShellRoot {
 id:root;property bool compact:true;property int phase:0
 QtObject {id:orphan;property real missingPadding:Tokens.padding.medium;property real missingScale:Config.appearance.scale}
 Timer {interval:300;running:true;onTriggered:{for(let i=0;i<5;i++){orphan.Tokens.padding.medium;orphan.Config.appearance.scale;}}}
 StyledWindow {
  id:win;name:"window-token-fixture";screen:Quickshell.screens[0];visible:true
  implicitWidth:300+Tokens.padding.large*2;implicitHeight:160
  property real directPadding:Tokens.padding.large
  ProfileImage {id:avatar;width:0;height:0}
  Item {id:item;width:40;height:40;property var modelData:({label:"Monitor tooltip"})
   QtObject {id:stateLayer;property bool containsMouse:true}
   __TOOLTIP__
  }
 }
 Timer {interval:700;running:true;repeat:true;onTriggered:{
  if(root.phase++===0){
   if(avatar.source.toString()!==""){console.error("WINDOW_TOKENS_FAILED","zero-size avatar started decoding");Qt.quit();return;}
   avatar.width=avatar.height=32;return;
  }
  if(avatar.status!==Image.Ready){console.error("WINDOW_TOKENS_FAILED","sized avatar did not decode");Qt.quit();return;}
  const expected=GlobalConfig.forScreen(win.screen.name).appearance.padding.large;
  const tipExpected=GlobalConfig.forScreen(win.screen.name).appearance.padding.medium;
  const result={tipPadding:navTip.padding,tipExpected:tipExpected,tipScreen:navTip.Tokens.screen,tipContentScreen:navTip.contentItem.Tokens.screen,tipBackgroundScreen:navTip.background.Tokens.screen,screen:win.screen.name,rootScreen:win.Tokens.screen,contentScreen:win.contentItem.Tokens.screen,rootPadding:win.directPadding,contentPadding:win.contentItem.Tokens.padding.large,expected:expected,globalPadding:GlobalConfig.appearance.padding.large};
  if(result.tipScreen!==result.screen||result.tipContentScreen!==result.screen||result.tipBackgroundScreen!==result.screen||result.tipPadding!==tipExpected||result.rootScreen!==result.screen||result.contentScreen!==result.screen||result.rootPadding!==expected||result.contentPadding!==expected||expected===result.globalPadding){console.error("WINDOW_TOKENS_FAILED",JSON.stringify(result));Qt.quit();return;}
  console.log("WINDOW_TOKENS_OK",JSON.stringify(result));Qt.quit();
 }}
}'''.replace('__TOOLTIP__',tooltip))
  env.update(WAYLAND_DISPLAY=instance['wl_socket'],HYPRLAND_INSTANCE_SIGNATURE=instance['instance'],QT_QPA_PLATFORM='wayland')
  env.update(snapshot_qml_runtime(ROOT,base))
  result=run_snapshot_qml(['/usr/share/hics/qs/bin/hics-qs','--path',str(entry)],env,ROOT/'build',15)
  output=result.stdout+result.stderr;Path('/tmp/hics-window-tokens.log').write_text(output)
  assert result.returncode==0 and 'WINDOW_TOKENS_OK' in output and 'WINDOW_TOKENS_FAILED' not in output,output[-5000:]
  assert output.count('Tokens.padding accessed without a screen set')==1,output[-5000:]
  assert output.count('Config.appearance accessed without a screen set')==1,output[-5000:]
  assert not any('accessed without a screen' in line and ('ToolTip' in line or 'StyledWindow' in line) for line in output.splitlines()),output[-5000:]
  print('PASS: layer-window sizing and content share the actual monitor padding/scale instead of global fallback')
 finally:
  if compositor and compositor.poll() is None:
   compositor.terminate()
   try:compositor.wait(timeout=5)
   except subprocess.TimeoutExpired:compositor.kill();compositor.wait()
