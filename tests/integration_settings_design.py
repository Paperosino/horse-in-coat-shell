#!/usr/bin/env python3
"""Render the real settings UI and verify disclosure, narrow forms and navigation."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
from integration_support import require_wayland_session, resize_nested_compositor
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
 property var shots:["dock","network","audio","display","shortcuts","session-recovery","touchpad","apps","app-info","keyboard","panels","region","storage","performance","application-rules","passwords","operations","backup","file-search","presentation"]
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
 function named(item,name){if(item.objectName===name)return item;for(const child of item.children??[]){const found=named(child,name);if(found)return found;}return null;}
 function check(value,message){if(!value){console.error("DESIGN_FAIL",message);Qt.exit(1);return false;}return true;}
 Component.onCompleted:{settings.nState.screen=Quickshell.screens[0];settings.nState.isWindow=true;}
 Timer {
  interval:400;repeat:true;running:true
  onTriggered:{
   if(root.phase<root.shots.length*2){
    const index=Math.floor(root.phase/2);
    if(root.phase%2===0){
     if(index>0&&root.shots[index-1]==="keyboard"&&Quickshell.env("HICS_TEST_WIDGET")){
      const characters=root.named(settings,"desktopCharacterPicker"),methods=root.named(settings,"desktopInputMethods");
      if(!root.check(characters?.items.length>0&&methods?.state.running&&methods.state.methods.length===2,"character picker or input method group controls did not load"))return;
     }
     root.narrow=root.shots[index]==="keyboard";
     if(root.shots[index]==="app-info") {
      settings.nState.openPage("apps");
      settings.nState.selectedApp={id:"org.hics.Fixture",name:"Application permissions",icon:"application-x-executable",filePath:"/usr/share/applications/org.hics.Fixture.desktop",command:[],comment:"",genericName:""};
      settings.nState.openSubPage(2);
     } else settings.nState.openPage(root.shots[index]);
    }
    else {
     if(root.shots[index]==="keyboard"&&Quickshell.env("HICS_TEST_WIDGET")){
      const characters=root.named(settings,"desktopCharacterPicker"),methods=root.named(settings,"desktopInputMethods");
      if(!root.check(!!characters&&!!methods,"text input settings are missing"))return;
      characters.expanded=true;characters.query="HEART";characters.category="symbols";characters.refresh();methods.expanded=true;methods.refresh();
     }
     if(root.shots[index]==="app-info" && !root.check(!!root.named(settings,"desktopApplicationPermissions"),"application permissions page did not load"))return;
     if(root.shots[index]==="presentation"){
      const dnd=Notifs.dnd,idle=IdleInhibitor.enabled;
      Presentation.begin(Quickshell.screens[0].name);
      if(!root.check(Presentation.active&&Presentation.privateOn(Quickshell.screens[0])&&!Presentation.privateOn({name:"other-fixture-output"})&&IdleInhibitor.effectiveEnabled&&!Notifs.shouldShowPopup(),"presentation policy did not activate"))return;
      Presentation.end();
      if(!root.check(!Presentation.active&&Notifs.dnd===dnd&&IdleInhibitor.enabled===idle,"presentation changed persistent preferences"))return;
     }
     if(root.shots[index]==="application-rules"){
      function findRulePage(item){if(item.form!==undefined && item.devicesOnly!==undefined)return item;for(const child of item.children??[]){const found=findRulePage(child);if(found)return found;}return null;}
      const page=findRulePage(settings);
      if(!root.check(!!page,"application rule editor did not load"))return;
      page.pickWindow({address:"0xfixture",application:"org.example.Code",title:"Editor"});
      if(!root.check(page.form.application==="org.example.Code" && page.form.title==="" && !page.form.regex,"open-window application picker failed"))return;
      page.pickWindow({address:"0xpip",application:"helium",title:"Picture-in-Picture"});
      if(!root.check(page.form.application==="helium" && page.form.title==="Picture-in-Picture","PiP window title selection failed"))return;
      page.form={application:"org.example.Code",name:"Code",mode:"stacking",titlebar:"hide",noShadow:false,rounding:12};
      page.preset("pip");
      if(!root.check(page.form.regex && new RegExp(page.form.application).test("org.example.Code") && !new RegExp(page.form.application).test("orgXexampleXCode") && page.form.pin,"PiP preset changed literal application matching"))return;
      page.form={application:"Code",name:"Code",mode:"stacking",titlebar:"hide",noShadow:false,rounding:12};
     }
     Qt.callLater(()=>settings.grabToImage(result=>result.saveToFile("/tmp/hics-settings-"+root.shots[index]+".png")));
    }
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
    if os.environ.get('HICS_TEST_WIDGET'):
        qml=(base/'shell/shell.qml').read_text()
        qml=qml.replace('import qs.modules.nexus\n','import qs.modules.nexus\nimport Hyprstack.Services\nimport qs.modules.bar.components\nimport qs.modules.bar.popouts as BarPopouts\n')
        qml=qml.replace(' property int phase:0',' property int phase:0\n property int widgetPhase:0\n property bool widgetDone:false')
        qml=qml.replace(' function check(value,message)',''' FloatingWindow {
  visible:true;implicitWidth:700;implicitHeight:200;color:Colours.palette.m3surface
  StatusIcons {id:statusWidget;anchors.centerIn:parent}
 }
 BarPopouts.PopoutState {id:operationPopouts;screen:Quickshell.screens[0]}
 FloatingWindow {
  visible:popupTest.active;implicitWidth:450;implicitHeight:600;color:Colours.palette.m3surface
  Loader {id:popupTest;active:false;anchors.fill:parent;sourceComponent:BarPopouts.Operations {popouts:operationPopouts}}
 }
 Timer {
  interval:400;repeat:true;running:!root.widgetDone
  onTriggered:{
   const phase=root.widgetPhase++;
   if(phase===0){GlobalConfig.utilities.operations.completedSeconds=1;GlobalConfig.utilities.operations.autoShow=true;GlobalConfig.utilities.operations.retainErrors=true;DesktopJobs.acknowledge();}
   if(phase===1)DesktopJobs.report("widget-fixture","transfer.copy","running",0.4);
   if(phase===2){if(!root.check(BackgroundOperations.visible&&BackgroundOperations.active.length===1&&Math.abs(BackgroundOperations.progress-0.4)<0.01,"automatic operations indicator did not show progress"))return;statusWidget.grabToImage(result=>result.saveToFile("/tmp/hics-operations-widget.png"));}
   if(phase===3)DesktopJobs.report("widget-fixture","transfer.copy","completed",1);
   if(phase===7){if(!root.check(!BackgroundOperations.visible,"completed operations indicator did not expire"))return;DesktopJobs.report("widget-error","transfer.send","running",0.2);}
   if(phase===8)DesktopJobs.report("widget-error","transfer.send","failed",0.2,"fixture failure");
   if(phase===10){if(!root.check(BackgroundOperations.visible&&BackgroundOperations.errors===1,"failed operation did not remain visible"))return;popupTest.active=true;}
   if(phase===11){if(!root.check(BackgroundOperations.openCount===1&&BackgroundOperations.visible&&popupTest.item.implicitHeight>0,"operations popout did not retain its anchor while reviewed"))return;popupTest.item.grabToImage(result=>{result.saveToFile("/tmp/hics-operations-popout.png");popupTest.active=false;});}
   if(phase===13){if(!root.check(!BackgroundOperations.visible,"reviewed error indicator did not disappear"))return;root.widgetDone=true;console.log("OPERATIONS_WIDGET_OK");}
  }
 }
 function check(value,message)''')
        qml=qml.replace('settings.grabToImage(result=>{result.saveToFile("/tmp/hics-settings-narrow-navigation.png");console.log("SETTINGS_DESIGN_OK");','if(!root.check(root.widgetDone,"widget checks did not complete"))return;settings.grabToImage(result=>{result.saveToFile("/tmp/hics-settings-narrow-navigation.png");console.log("SETTINGS_DESIGN_OK");')
        (base/'shell/shell.qml').write_text(qml)
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
        resize_nested_compositor(compositor.pid)
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
