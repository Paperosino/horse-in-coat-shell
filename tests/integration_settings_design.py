#!/usr/bin/env python3
"""Render the real settings UI and verify disclosure, narrow forms and navigation."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
from integration_support import require_wayland_session
require_wayland_session()
ROOT=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='hics-settings-design-') as directory:
    base=Path(directory);shutil.copytree(ROOT/'shell',base/'shell',ignore=shutil.ignore_patterns('plugin','extras','__pycache__'))
    (base/'config/hics').mkdir(parents=True)
    (base/'config/hics/shell.json').write_text('{"appearance":{"reducedMotion":true}}')
    (base/'shell/shell.qml').write_text('''import QtQuick
import QtQuick.Layouts
import Quickshell
import Hyprstack.Config
import qs.components
import qs.modules.nexus
import qs.modules.nexus.common
import qs.services
ShellRoot {
 id:root
 property int phase:0
 property bool narrow:false
 property bool controlledExpanded:false
 property var shots:["dock","network","audio","display","shortcuts","session-recovery","touchpad","apps","keyboard","panels","region","storage"]
 FloatingWindow {
  id:win;visible:true;implicitWidth:1180;implicitHeight:820;color:Colours.palette.m3surface
  Nexus {id:settings;width:root.narrow?560:parent.width;height:parent.height;visible:!fixture.visible}
  PageBase {
   id:fixture;x:20;y:20;width:root.narrow?360:parent.width-40;height:parent.height-40;visible:false;title:"Design regression";nState:settings.nState
   ColumnLayout {
    width:fixture.cappedWidth;anchors.horizontalCenter:parent.horizontalCenter
    Repeater {model:20;InfoRow {label:"Position";value:"Retained while a section opens"}}
    SettingsCard {
     id:advanced;title:"Advanced";icon:"settings";collapsible:true;expanded:root.controlledExpanded;expansionHandler:value=>root.controlledExpanded=value
     TextFieldRow {id:field;objectName:"designAdvancedField";label:"Long setting label which must remain readable on a narrow screen";value:"Preserved"}
    }
   }
  }
 }
 function check(value,message){if(!value){console.error("DESIGN_FAIL",message);Qt.exit(1);return false;}return true;}
 Component.onCompleted:{settings.nState.screen=Quickshell.screens[0];settings.nState.isWindow=true;}
 Timer {
  interval:400;repeat:true;running:true
  onTriggered:{
   if(root.phase<root.shots.length*2){
    const index=Math.floor(root.phase/2);
    if(root.phase%2===0)settings.nState.openPage(root.shots[index]);
    else settings.grabToImage(result=>result.saveToFile("/tmp/hics-settings-"+root.shots[index]+".png"));
   } else {
    const step=root.phase-root.shots.length*2;
    if(step===0){fixture.visible=true;fixture.nState.searchTarget="designAdvancedField";fixture.searchAttempts=0;fixture.searchRetry.restart();}
    if(step===1){if(!root.check(advanced.expanded,"search did not expand advanced controls"))return;if(!root.check(field.value==="Preserved","disclosure lost field data"))return;root.narrow=true;}
    if(step===2){if(!root.check(field.width<360 && field.field.width>100 && field.field.width<=field.width,"narrow field exceeds card bounds"))return;advanced.changeExpansion(false);}
    if(step===3){if(!root.check(!advanced.expanded && field.value==="Preserved","collapse mutated settings"))return;advanced.changeExpansion(true);root.controlledExpanded=false;if(!root.check(!advanced.expanded,"disclosure broke the external model binding"))return;advanced.changeExpansion(true);GlobalConfig.appearance.highContrast=true;}
    if(step===4){if(!root.check(advanced.expanded,"reduce-motion disclosure did not finish"))return;fixture.grabToImage(result=>{result.saveToFile("/tmp/hics-settings-narrow.png");fixture.visible=false;settings.nState.openPage("network");settings.nState.openPage("audio");settings.nState.openPage("dock");});}
    if(step===5){
     function find(item){if(item.pageIcon==="dock_to_bottom" && item.title)return true;for(const child of item.children??[])if(find(child))return true;return false;}
     if(!root.check(find(settings),"rapid navigation attached a stale page"))return;
     settings.grabToImage(result=>{result.saveToFile("/tmp/hics-settings-narrow-navigation.png");console.log("SETTINGS_DESIGN_OK");Qt.quit();});
    }
   }
   root.phase++;
  }
 }
}''')
    # Timer searchRetry is intentionally private to PageBase; call the public
    # reveal routine repeatedly once the new page has settled instead.
    p=base/'shell/shell.qml';p.write_text(p.read_text().replace('fixture.searchAttempts=0;fixture.searchRetry.restart();','fixture.revealSearchTarget();'))
    (base/'compositor.lua').write_text('hl.monitor({output="WAYLAND-1",mode="1280x900@60",position="0x0",scale=1})\n')
    env=dict(os.environ,AQ_BACKEND='wayland',XDG_CONFIG_HOME=str(base/'config'),XDG_STATE_HOME=str(base/'state'),XDG_DATA_HOME=str(base/'data'),XDG_CACHE_HOME=str(base/'cache'))
    env.pop('HYPRLAND_INSTANCE_SIGNATURE',None)
    compositor=None
    try:
        log=(base/'compositor.log').open('w');compositor=subprocess.Popen(['Hyprland','--config',str(base/'compositor.lua')],env=env,stdout=log,stderr=subprocess.STDOUT)
        instance=None
        for _ in range(80):
            instance=next((i for i in json.loads(subprocess.check_output(['hyprctl','instances','-j'])) if i['pid']==compositor.pid),None)
            if instance:break
            time.sleep(.1)
        assert instance,'No nested compositor'
        env.update(WAYLAND_DISPLAY=instance['wl_socket'],HYPRLAND_INSTANCE_SIGNATURE=instance['instance'],QML_IMPORT_PATH=str(ROOT/'build/qml'),QML2_IMPORT_PATH=str(ROOT/'build/qml'),QT_QPA_PLATFORM='wayland')
        result=subprocess.run(['/usr/share/hics/qs/bin/hics-qs','-p',str(base/'shell')],env=env,capture_output=True,text=True,timeout=45)
        output=result.stdout+result.stderr
        (Path('/tmp/hics-settings-design-render.log')).write_text(output)
        assert result.returncode==0 and 'SETTINGS_DESIGN_OK' in output,output[-7000:]
        # Qt destroys global menu contexts after Qt.quit; only reject live UI warnings.
        live=output.split('SETTINGS_DESIGN_OK')[0]
        assert not any(s in live for s in ('TypeError:','ReferenceError:','Binding loop','Cannot assign','Unable to assign')),live[-7000:]
        print('PASS: live settings screenshots, searchable disclosure, narrow forms, reduced motion, high contrast and rapid navigation')
    finally:
        if compositor:
            compositor.terminate()
            try:compositor.wait(timeout=5)
            except subprocess.TimeoutExpired:compositor.kill();compositor.wait()
