#!/usr/bin/env python3
"""Real settings and compositor option restoration in an isolated session."""
import json,os,shutil,subprocess,tempfile,time
from pathlib import Path
from integration_support import require_wayland_session
require_wayland_session()
ROOT=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='hics-performance-ui-') as directory:
 base=Path(directory);shutil.copytree(ROOT/'shell',base/'shell',ignore=shutil.ignore_patterns('plugin','extras','__pycache__'))
 (base/'shell/shell.qml').write_text('''import QtQuick
import Quickshell
import Hyprstack.Services
import Hyprstack.Config
import qs.modules.nexus
import qs.modules.nexus.pages
import qs.services
ShellRoot {
 id:root;property int phase:0;property bool narrow:false;property var original:({});property int rounds:0
 NexusState {id:state;screen:Quickshell.screens[0];isWindow:true}
 FloatingWindow {id:win;visible:true;implicitWidth:root.narrow?560:1120;implicitHeight:820;color:Colours.palette.m3surface
  PerformancePage {id:page;anchors.horizontalCenter:parent.horizontalCenter;width:root.narrow?540:parent.width;height:parent.height;nState:state}
 }
 function require(value,message){if(!value){console.error("PERFORMANCE_FAIL",message);Qt.exit(1);return false;}return true;}
 function game(fullscreen,pid){RuntimePerformance.observeWindow({class:"org.test.Game",mapped:true,pid:pid,fullscreen:fullscreen});}
 function cards(item,result){if(item.settingsCard)result.push(item);for(const child of item.children??[])cards(child,result);}
 Timer {interval:200;repeat:true;running:true;onTriggered:{
  if(++root.rounds>90){console.error("PERFORMANCE_TIMEOUT",root.phase,JSON.stringify(Hypr.options));Qt.exit(1);return;}
  switch(root.phase){
   case 0:
    if(Hypr.options["render:direct_scanout"]===undefined)return;
    root.original={gaps:Hypr.options["general:gaps_in"],scanout:Hypr.options["render:direct_scanout"],tearing:Hypr.options["general:allow_tearing"]};
    RuntimePerformance.set("gameRules",["org.test.Game"]);RuntimePerformance.set("autoGameMode",true);root.game(1,12345);
    if(!root.require(!RuntimePerformance.autoGame&&!GameMode.enabled,"maximised window classified as a fullscreen game"))return;
    root.game(2,12345);root.phase=1;break;
   case 1:
    if(!GameMode.enabled||String(Hypr.options["general:gaps_in"])!=="0 0 0 0")return;
    RuntimePerformance.setSessionState(true,false,false);
    if(!root.require(Cpu.updateInterval===GlobalConfig.dashboard.resourceUpdateInterval*5,"game telemetry did not throttle"))return;
    GameMode.enabled=false;root.phase=2;break;
   case 2:
    if(GameMode.enabled||Hypr.options["general:gaps_in"]!==root.original.gaps)return;
    RuntimePerformance.setSessionState(false,false,false);
    if(!root.require(Cpu.updateInterval===GlobalConfig.dashboard.resourceUpdateInterval,"game telemetry interval did not restore"))return;
    root.game(2,12345);if(!root.require(!GameMode.enabled,"manual disable was overridden"))return;
    root.game(1,12345);root.game(2,12345);if(!root.require(!GameMode.enabled,"fullscreen transition cleared manual disable"))return;
    RuntimePerformance.observeWindow({});root.game(2,12345);if(!root.require(!GameMode.enabled,"focus round trip cleared manual disable"))return;
    RuntimePerformance.observeWindow({});root.game(2,23456);root.phase=3;break;
   case 3:
    if(!GameMode.enabled||String(Hypr.options["general:gaps_in"])!=="0 0 0 0")return;
    RuntimePerformance.set("disableEffects",false);root.phase=4;break;
   case 4:
    if(Hypr.options["general:gaps_in"]!==root.original.gaps)return;
    RuntimePerformance.set("directScanout",1);RuntimePerformance.set("allowTearing",true);root.phase=5;break;
   case 5:
    if(Number(Hypr.options["render:direct_scanout"])!==2||Number(Hypr.options["general:allow_tearing"])!==1)return;
    RuntimePerformance.observeWindow({});root.phase=6;break;
   case 6:
    if(GameMode.enabled||Hypr.options["render:direct_scanout"]!==root.original.scanout||Hypr.options["general:allow_tearing"]!==root.original.tearing)return;
    RuntimePerformance.set("autoGameMode",false);RuntimePerformance.set("disableEffects",true);
    const found=[];root.cards(page,found);if(!root.require(found.length>=7,"missing performance cards"))return;
    for(const card of found)card.expanded=true;
    root.phase=7;break;
   case 7:
    if(page.layoutAnimations.length)return;
    page.grabToImage(result=>result.saveToFile("/tmp/hics-performance-settings.png"));root.narrow=true;root.phase=8;break;
   case 8:
    if(page.layoutAnimations.length)return;
    page.preferredContentY=Math.max(0,page.flickable.contentHeight-page.flickable.height+page.flickable.bottomMargin);
    page.flickable.contentY=page.preferredContentY;root.phase=9;break;
   case 9:
    if(!root.require(page.width<=540 && page.flickable.contentY>1000 && page.flickable.contentY+page.flickable.height>=page.flickable.contentHeight-2,"narrow advanced settings cannot reach the final card"))return;
    page.grabToImage(result=>{result.saveToFile("/tmp/hics-performance-settings-narrow.png");console.log("PERFORMANCE_UI_OK");Qt.quit();});root.phase=10;break;
  }
 }}
}''')
 (base/'test.lua').write_text('hl.monitor({output="WAYLAND-1",mode="1280x900@60",position="0x0",scale=1})\n')
 env=dict(os.environ,HICS_HELPER_DIR=str(ROOT/'build/native/system'),AQ_BACKEND='wayland',XDG_CONFIG_HOME=str(base/'config'),XDG_STATE_HOME=str(base/'state'),XDG_CACHE_HOME=str(base/'cache'),XDG_DATA_HOME=str(base/'data'));env.pop('HYPRLAND_INSTANCE_SIGNATURE',None)
 compositor=None
 try:
  with (base/'compositor.log').open('w') as log:compositor=subprocess.Popen(['Hyprland','--config',str(base/'test.lua')],env=env,stdout=log,stderr=subprocess.STDOUT)
  for _ in range(80):
   instance=next((i for i in json.loads(subprocess.check_output(['hyprctl','instances','-j'])) if i['pid']==compositor.pid),None)
   if instance:break
   time.sleep(.1)
  assert instance,'Nested compositor did not start'
  env.update(WAYLAND_DISPLAY=instance['wl_socket'],HYPRLAND_INSTANCE_SIGNATURE=instance['instance'],QML_IMPORT_PATH=str(ROOT/'build/qml'),QML2_IMPORT_PATH=str(ROOT/'build/qml'),QT_QPA_PLATFORM='wayland')
  run=subprocess.run(['/usr/share/hics/qs/bin/hics-qs','-p',str(base/'shell')],env=env,capture_output=True,text=True,timeout=24)
  output=run.stdout+run.stderr;Path('/tmp/hics-performance-ui.log').write_text(output)
  assert run.returncode==0 and 'PERFORMANCE_UI_OK' in output,output[-7000:]
  assert not any(s in output for s in ('TypeError:','ReferenceError:','Binding loop','Cannot assign','Unable to assign')),output[-7000:]
  print('PASS: automatic game mode, manual override, live preference changes, scanout/tearing restoration, animated cards and narrow scrolling')
 finally:
  if compositor and compositor.poll() is None:
   compositor.terminate()
   try:compositor.wait(timeout=5)
   except subprocess.TimeoutExpired:compositor.kill();compositor.wait()
