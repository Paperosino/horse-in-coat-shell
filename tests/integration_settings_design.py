#!/usr/bin/env python3
"""Render the real settings UI and verify disclosure, narrow forms and navigation."""
import json
import ast
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
 property int hierarchyPhase:0
 property bool hierarchyDone:false
 property int layoutAttempts:0
 property int phase:0
 property bool narrow:false
 property bool controlledExpanded:false
 property var shots:["dock","network","audio","display","shortcuts","session-recovery","touchpad","apps","app-info","keyboard","panels","statusbar-layout","panel-options","panel-status-icons","region","storage","performance","application-rules","passwords","operations","backup","file-search","presentation","focus","file-integration","accessibility","clipboard","bluetooth","power","accounts","firmware","tablets","colour-profiles","configuration-history","about"]
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
   if(!root.hierarchyDone){
    const step=root.hierarchyPhase++;
    if(step===0){
     if(!root.check(PageRegistry.sections.length===10 && settings.nState.showingSection,"settings must open at Home with ten sidebar categories"))return;
     const ids=PageRegistry.navigationPages.map(page=>page.id);
     if(!root.check(ids.every((id,index)=>ids.indexOf(id)===index) && PageRegistry.navigationPages.every(page=>page.pageIndex>=0),"categories contain duplicated or invalid pages"))return;
     settings.grabToImage(result=>{result.saveToFile("/tmp/hics-settings-home.png");settings.nState.openSection("system");});
    }
    if(step===1){
     if(!root.check(!!root.named(settings,"settingsSectionOverview"),"system overview did not load"))return;
     const link=root.named(settings,"settings-link-storage");
     if(!root.check(!!link,"storage is missing from System"))return;
     settings.grabToImage(result=>{result.saveToFile("/tmp/hics-settings-system-overview.png");link.clicked();});
    }
    if(step===2){if(!root.check(!settings.nState.showingSection && settings.nState.sectionId==="system" && PageRegistry.pages[settings.nState.currentPageIdx].id==="storage","category link did not open its settings"))return;settings.nState.goBack();}
    if(step===3){if(!root.check(settings.nState.showingSection && settings.nState.sectionId==="system","Back did not restore the category"))return;root.narrow=true;settings.nState.openSection("personalisation");}
    if(step===4){if(!root.check(settings.compactNavigation,"narrow settings did not collapse navigation"))return;settings.grabToImage(result=>{result.saveToFile("/tmp/hics-settings-category-narrow.png");settings.nState.openPage("themes");});}
    if(step===5){if(!root.check(!settings.nState.showingSection&&settings.nState.subPageIdxStack[0]===4,"saved theme route did not open its detail page"))return;settings.nState.goBack();}
    if(step===6){if(!root.check(settings.nState.subPageIdxStack.length===0,"Back did not close the detail page"))return;settings.nState.goBack();}
    if(step===7){if(!root.check(settings.nState.showingSection&&settings.nState.sectionId==="personalisation","Back lost the source category"))return;settings.nState.openPage("appearance");}
    if(step===8){if(!root.check(!settings.nState.showingSection&&PageRegistry.pages[settings.nState.currentPageIdx].id==="appearance","same-index page opening remained stuck on the category"))return;root.narrow=false;settings.nState.openPage("audio");}
    if(step===9)settings.nState.openPage("themes");
    if(step===10 && !root.check(settings.nState.subPageIdxStack[0]===4,"a stale stack consumed another page detail route"))return;
    if(step===11)settings.nState.openSection("home");
    const categories=["devices","connections","applications","language","accessibility","privacy","maintenance"];
    if(step>=12 && step<12+categories.length*2){
     const index=Math.floor((step-12)/2),id=categories[index];
     if((step-12)%2===0)settings.nState.openSection(id);
     else if(!root.check(settings.nState.sectionId===id && (PageRegistry.section(id).landing || !!root.named(settings,"settingsSectionOverview")),"category failed to load: "+id))return;
    }
    if(step===12+categories.length*2){root.hierarchyDone=true;settings.nState.openSection("home");console.log("SETTINGS_HIERARCHY_OK");}
    return;
   }
   if(root.phase<root.shots.length*2){
    const index=Math.floor(root.phase/2);
    if(root.phase%2===0){
     if(index>0&&root.shots[index-1]==="keyboard"&&Quickshell.env("HICS_TEST_WIDGET")){
      const characters=root.named(settings,"desktopCharacterPicker"),methods=root.named(settings,"desktopInputMethods");
      if(!root.check(characters?.items.length>0&&methods?.state.running&&methods.state.methods.length===2,"character picker or input method group controls did not load"))return;
     }
     root.narrow=["keyboard","statusbar-layout"].includes(root.shots[index]);
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
     if(root.shots[index]==="statusbar-layout"){
      function panelPage(item){if(item.widgetZone!==undefined && item.allCatalogWidgets!==undefined)return item;for(const child of item.children??[]){const found=panelPage(child);if(found)return found;}return null;}
      const page=panelPage(settings);
      if(!root.check(!!page,"panel widget editor did not load"))return;
      page.addWidget(0,"clock");page.addWidget(2,"clock");
      if(!root.check([...page.leftWidgets,...page.centerWidgets,...page.rightWidgets].filter(id=>id==="clock").length===1 && page.widgetZone("clock")===2,"moving a widget duplicated it"))return;
      page.addWidget(-1,"notifications");page.reloadZones();
      if(!root.check(page.widgetZone("notifications")===-1 && page.editedBar.entries.values.some(entry=>entry.id==="notifications"&&!entry.enabled),"removed notification widget was resurrected"))return;
      page.saveZones([],[],[]);page.reloadZones();
      if(!root.check(!page.leftWidgets.length&&!page.centerWidgets.length&&!page.rightWidgets.length,"empty panel restored unwanted default widgets"))return;
      page.saveZones(["logo","workspaces"],["clock"],["tray","statusIcons","power"]);
      page.flickable.contentY=Math.max(0,page.flickable.contentHeight-page.flickable.height);
     }
     if(root.shots[index]==="app-info"){
      const permissions=root.named(settings,"desktopApplicationPermissions");
      if(permissions){
       const armor=root.named(permissions,"appArmorSettings");
       if(armor)armor.expanded=true;
       permissions.armor={apparmorActive:true,apparmorServiceEnabled:true,profileFiles:["usr.bin.fixture"],profiles:["fixture (enforce)"]};
       permissions.selectedProfile="usr.bin.fixture";
       permissions.policy={profile:"usr.bin.fixture",sha256:"fixture",localSha256:"fixture",guiSupported:true};
       permissions.restrictions={network:true,camera:false,audio:false,home:false,removable:false};
       const controls=root.named(permissions,"appArmorVisualRestrictions");
       if(!root.check(!!controls&&controls.visible,"visual AppArmor controls missing"))return;
      }
     }
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
      page.form={};
      page.pickWindow({address:"0xignored",application:"ShouldNotCreate",title:"Ignored"});
      if(!root.check(Object.keys(page.form).length===0,"picker created a rule outside the editor"))return;
      page.editRule({id:"existing-chatgpt",name:"ChatGPT",application:"AI",mode:"stacking",titlebar:"hide",enabled:false,rounding:12});
      if(!root.check(!!root.named(settings,"ruleWindowMatcher"),"window picker is not inside the editor"))return;
      page.pickWindow({address:"0xfixture",application:"org.example.Code",title:"Editor",xwayland:true});
      if(!root.check(page.form.id==="existing-chatgpt"&&page.form.name==="ChatGPT"&&page.form.mode==="stacking"&&page.form.titlebar==="hide"&&page.form.enabled===false&&page.form.rounding===12,"window selection changed existing rule properties"))return;
      if(!root.check(page.form.application==="org.example.Code" && page.form.title==="" && !page.form.regex && page.form.matchXwayland===true,"open-window application picker failed"))return;
      page.pickWindow({address:"0xpip",application:"helium",title:"Picture-in-Picture",xwayland:false});
      if(!root.check(page.form.application==="helium" && page.form.title==="Picture-in-Picture" && page.form.matchXwayland===false,"PiP window title selection failed"))return;
      page.pickWindow({address:"0xdialog",application:"helium",title:"Document",initialTitle:"Open File"});
      page.setScope("initial");
      if(!root.check(page.form.initialTitle==="Open File"&&page.form.title==="","initial-title window type selection failed"))return;
      page.pickApplication("helium");
      if(!root.check(!page.selectedWindow&&page.form.title===""&&page.form.initialTitle==="","application selection retained a window-specific match"))return;
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
    if(step===2){const fits=field.width<360 && field.field.width>100 && field.field.width<=field.width;if(!fits&&root.layoutAttempts++<10)return;if(!root.check(fits,"narrow field exceeds card bounds: "+field.width+" / "+field.field.width+" ancestors "+[field.parent,field.parent?.parent,field.parent?.parent?.parent,advanced,fixture.contentChild,fixture].map(item=>item?String(item)+":"+item.width+":"+item.visible+":"+item.implicitHeight:"null").join("; ")))return;advanced.changeExpansion(false);}
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
    if os.environ.get('HICS_TEST_WIDGET'):
        p=base/'shell/shell.qml';qml=p.read_text().replace('import Hyprstack.Services\n','import Hyprstack.Services\nimport Hyprstack\nimport Quickshell.Io\n',1)
        qml=qml.replace(' property int phase:0',' property bool featuresDone:false\n property var savedComfort:({})\n property bool savedDnd:false\n property bool savedIdle:false\n property int phase:0',1)
        qml=qml.replace('   if(!root.hierarchyDone){','   if(!root.featuresDone)return;\n   if(!root.hierarchyDone){',1)
        qml=qml.replace(' function named(item,name)',''' Process {id:plainReader;command:["wl-paste","--no-newline","--type","text/plain"];stdout:StdioCollector {id:plainResult}}
 Process {id:plainProvider;command:["wl-copy","--type","text/plain;charset=utf-8"];stdinEnabled:true;onStarted:{write("Plain café fixture");stdinEnabled=false;}}
 QtObject {id:layoutKeyboard;property string layout:"us,ru";property var lastIpcObject:({active_layout_index:0,variant:""})}
 QtObject {id:layoutExtras;function request(command,callback){const index=Number(command.split(" ").pop());layoutKeyboard.lastIpcObject={active_layout_index:index,variant:""};layoutHypr.kbLayoutFull=index===0?"English":"Russian";callback(true,"ok");}}
 QtObject {id:layoutHypr;property var keyboard:layoutKeyboard;property var extras:layoutExtras;property string kbLayout:"us";property string kbLayoutFull:"English";property var activeToplevel:({lastIpcObject:{class:"FixtureA"}})}
 Timer {
  property int step:0
  interval:400;repeat:true;running:!root.featuresDone
  onTriggered:{
   const phase=step++;
   if(phase===0){
    root.savedDnd=Notifs.dnd;root.savedIdle=IdleInhibitor.enabled;
    root.savedComfort={applicationLayouts:GlobalConfig.utilities.comfort.applicationLayouts,quietDuringCalls:GlobalConfig.utilities.comfort.quietDuringCalls,cursorLocatorSeconds:GlobalConfig.utilities.comfort.cursorLocatorSeconds,settingsPins:Array.from(GlobalConfig.utilities.comfort.settingsPins)};
    DesktopJobs.request("comfort.focus-start",{minutes:1,quiet:true,keepAwake:true});
   }
   if(phase===1){if(!root.check(Comfort.focusing&&Comfort.quiet&&IdleInhibitor.effectiveEnabled&&!Notifs.shouldShowPopup()&&root.named(statusWidget,"focusTimerIndicator").visible,"focus policy or panel timer did not activate"))return;DesktopJobs.request("comfort.focus-pause",{});}
   if(phase===2){if(!root.check(!!Comfort.focus.paused&&!Comfort.focusing&&Notifs.dnd===root.savedDnd,"pausing focus changed persistent settings"))return;DesktopJobs.request("comfort.focus-resume",{});}
   if(phase===3){if(!root.check(Comfort.focusing&&Notifs.shouldShowPopup(true),"resumed focus or its break reminder policy failed"))return;DesktopJobs.request("comfort.awake",{minutes:30});DesktopJobs.request("comfort.focus-stop",{});}
   if(phase===4){if(!root.check(Comfort.awake&&!Comfort.focusing&&IdleInhibitor.enabled===root.savedIdle,"focus stop destroyed an independent temporary wake lock"))return;DesktopJobs.request("comfort.awake",{minutes:0});GlobalConfig.utilities.comfort.quietDuringCalls=true;Comfort.recordingStreams=[{}];}
   if(phase===5){if(!root.check(Comfort.callActive&&!Notifs.shouldShowPopup()&&Notifs.dnd===root.savedDnd,"automatic recording quiet mode changed user DND"))return;Comfort.recordingStreams=[];ApplicationLayouts.backend=layoutHypr;GlobalConfig.utilities.comfort.applicationLayouts=true;ApplicationLayouts.focus();}
   if(phase===6){if(!root.check(!Comfort.callActive&&!Comfort.awake,"temporary policies did not stop"))return;layoutKeyboard.lastIpcObject={active_layout_index:1,variant:""};layoutHypr.kbLayoutFull="Russian";}
   if(phase===7){layoutHypr.activeToplevel={lastIpcObject:{class:"FixtureB"}};}
   if(phase===8){layoutKeyboard.lastIpcObject={active_layout_index:0,variant:""};layoutHypr.kbLayoutFull="English";}
   if(phase===9){layoutHypr.activeToplevel={lastIpcObject:{class:"FixtureA"}};}
   if(phase===10){if(!root.check(layoutKeyboard.lastIpcObject.active_layout_index===1&&ApplicationLayouts.memory.FixtureB===0,"per-application keyboard layout restoration failed"))return;GlobalConfig.utilities.comfort.applicationLayouts=false;ApplicationLayouts.backend=Hypr;CursorLocator.show();}
   if(phase===11){if(!root.check(!!CursorLocator.output,"native pointer locator did not map an output"))return;GlobalConfig.utilities.comfort.cursorLocatorSeconds=1;CursorLocator.show();const device={address:"battery-fixture",name:"Fixture headset",connected:true,batteryAvailable:true,battery:0.1};Comfort.checkBattery(device);const count=Toaster.toasts.length;Comfort.checkBattery(device);if(!root.check(Toaster.toasts.length===count,"Bluetooth battery warning repeated without recharging"))return;device.battery=0.9;Comfort.checkBattery(device);if(!root.check(!Comfort.warnedBatteries[device.address],"recharging did not rearm the battery reminder"))return;}
   if(phase===12){settings.nState.openPage("audio");}
   if(phase===13){const pin=root.named(settings,"settingsPinButton");if(!root.check(!!pin,"settings pin control is missing"))return;GlobalConfig.utilities.comfort.settingsPins=[];pin.clicked();}
   if(phase===14){if(!root.check(GlobalConfig.utilities.comfort.settingsPins.includes("audio")&&!CursorLocator.output,"pinning or automatic pointer highlight expiry failed"))return;settings.nState.openSection("home");}
   if(phase===15){if(!root.check(!!root.named(settings,"settings-link-audio"),"pinned page did not appear on settings home"))return;for(const key of Object.keys(root.savedComfort))GlobalConfig.utilities.comfort[key]=root.savedComfort[key];Comfort.recordingStreams=Qt.binding(()=>Audio.microphoneStreams);plainProvider.running=true;}
   if(phase===16){DesktopJobs.request("comfort.plain-text",{},value=>{if(!root.check(!value.error,"native clipboard conversion failed: "+value.error))return;});}
   if(phase===17){plainReader.running=true;}
   if(phase===18){if(!root.check(DesktopJobs.available&&plainResult.text==="Plain café fixture","clipboard conversion failed to preserve Unicode text"))return;root.featuresDone=true;console.log("DESKTOP_COMFORT_OK");}
  }
 }
 function named(item,name)''',1)
        p.write_text(qml)
    # Timer searchRetry is intentionally private to PageBase; call the public
    # reveal routine repeatedly once the new page has settled instead.
    p=base/'shell/shell.qml';p.write_text(p.read_text().replace('fixture.searchAttempts=0;fixture.searchRetry.restart();','fixture.revealSearchTarget();'))
    if os.environ.get('HICS_TEST_PANEL_CONTROLS'):
        (base/'shell/shell.qml').write_text((ROOT/'tests/fixtures/panel-controls.qml').read_text())
    if os.environ.get('HICS_TEST_RECOVERY'):
        stub=base/'recovery-stub.py'
        stub.write_text('import json,sys,time\nprint(json.dumps({"startupCheckpoint":{"available":True},"pending":{"token":"fixture","deadline":time.time()+30} if sys.argv[1]=="restore" else {},"restarting":sys.argv[1]=="resume"}))\n')
        fixture=(ROOT/'shell/recovery/shell.qml').read_text()
        if os.environ.get('HICS_TEST_RECOVERY_LOCALE')=='ru':fixture=fixture.replace('Qt.locale().name.startsWith("ru")','true')
        fixture=fixture.replace('Component.onCompleted: invoke("status")','Component.onCompleted: {root.helperCommand=["python3",'+json.dumps(str(stub))+'];root.invoke("status");}')
        checks="""
 property int phase:0
 function named(item,name){if(item.objectName===name)return item;for(const child of item.children??[]){const found=named(child,name);if(found)return found;}return null;}
 Timer {interval:350;running:true;repeat:true;onTriggered:{
  if(worker.running)return;
  if(root.phase===0){if(!root.data.startupCheckpoint?.available)throw new Error("Missing startup checkpoint");root.named(recoveryContent,"restoreStartup").clicked();if(!root.confirmation)throw new Error("Recovery must require review");}
  if(root.phase===1)root.named(recoveryContent,"restoreStartup").clicked();
  if(root.phase===2){if(!root.data.pending?.token||root.remaining<1||root.remaining>30)throw new Error("No timed guarded restore");recoveryContent.grabToImage(result=>result.saveToFile("/tmp/hics-recovery-mode.png"));root.named(recoveryContent,"resumeStartup").clicked();}
  if(root.phase===3){if(!root.data.restarting)throw new Error("Resume missing");console.log("SETTINGS_DESIGN_OK RECOVERY_MODE_OK");Qt.quit();}
  root.phase++;
 }}
"""
        fixture=fixture[:fixture.rfind('}')]+checks+'}\n'
        (base/'shell/shell.qml').write_text(fixture)
        (base/'config/hics/shell.json').write_bytes(b'{intentionally broken')
    if os.environ.get('HICS_TEST_FONT_RENDERING'):
        fixture=(ROOT/'tests/fixtures/font-rendering.qml').read_text()
        if os.environ['HICS_TEST_FONT_RENDERING']=='narrow':fixture=fixture.replace('implicitWidth: 1000','implicitWidth: 560')
        fixture=fixture.replace('/tmp/hics-icon-policy-',str(base/'icon-policy-'))
        (base/'shell/shell.qml').write_text(fixture)
    if os.environ.get('HICS_TEST_SCALING'):
        (base/'config/hics/shell.json').write_text('{"appearance":{"reducedMotion":true,"font":{"hinting":"none"}}}')
        (base/'shell/shell.qml').write_text((ROOT/'tests/fixtures/scaling-quality.qml').read_text())
    (base/'compositor.lua').write_text('hl.monitor({output="WAYLAND-1",mode="1280x900@60",position="0x0",scale=1})\n')
    env=dict(os.environ,AQ_BACKEND='wayland',XDG_CONFIG_HOME=str(base/'config'),XDG_STATE_HOME=str(base/'state'),XDG_DATA_HOME=str(base/'data'),XDG_CACHE_HOME=str(base/'cache'))
    env.pop('HYPRLAND_INSTANCE_SIGNATURE',None)
    if os.environ.get('HICS_TEST_RECOVERY'):env['FONTCONFIG_FILE']=str(ROOT/'shell/recovery/fonts.conf')
    compositor=None
    desktop_daemon=None
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
        if os.environ.get('HICS_TEST_NATIVE_DESKTOP'):
            desktop_daemon=subprocess.Popen([str(ROOT/'build/native/desktop/hics-desktopd')],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            for _ in range(100):
                owner=subprocess.check_output(['gdbus','call','--session','--dest','org.freedesktop.DBus','--object-path','/org/freedesktop/DBus','--method','org.freedesktop.DBus.NameHasOwner','org.hics.Desktop1'],env=env,text=True)
                if 'true' not in owner:
                    time.sleep(.03)
                    continue
                ready=subprocess.run(['gdbus','call','--session','--dest','org.hics.Desktop1','--object-path','/org/hics/Desktop1','--method','org.hics.Desktop1.Status'],env=env,capture_output=True,text=True)
                if ready.returncode==0:break
                time.sleep(.05)
            assert ready.returncode==0,'Nested desktop daemon not ready'
            for operation in ['diagnostics.check','unknown.fixture']:
                subprocess.run(['gdbus','call','--session','--dest','org.hics.Desktop1','--object-path','/org/hics/Desktop1','--method','org.hics.Desktop1.Start',operation,'{}'],env=env,capture_output=True,check=True)
        result=subprocess.run(['/usr/share/hics/qs/bin/hics-qs','-p',str(base/'shell')],env=env,capture_output=True,text=True,timeout=65)
        output=result.stdout+result.stderr
        (Path('/tmp/hics-settings-design-render.log')).write_text(output)
        assert result.returncode==0 and 'SETTINGS_DESIGN_OK' in output,output[-7000:]
        if os.environ.get('HICS_TEST_FONT_RENDERING'):
            from PIL import Image
            images=[Image.open(base/f'icon-policy-{index}.png').convert('RGBA') for index in range(8)]
            assert all(image.size==images[0].size and image.tobytes()==images[0].tobytes() for image in images), 'Text rendering preferences changed the icon raster'
        # Qt destroys global menu contexts after Qt.quit; only reject live UI warnings.
        live=output.split('SETTINGS_DESIGN_OK')[0]
        assert not any(s in live for s in ('TypeError:','ReferenceError:','Binding loop','Cannot assign','Unable to assign')),live[-7000:]
        print('PASS: live settings screenshots, searchable disclosure, narrow forms, reduced motion, high contrast and rapid navigation')
    finally:
        if desktop_daemon:
            desktop_daemon.terminate()
            try:desktop_daemon.wait(timeout=5)
            except subprocess.TimeoutExpired:desktop_daemon.kill();desktop_daemon.wait()
        if compositor:
            compositor.terminate()
            try:compositor.wait(timeout=5)
            except subprocess.TimeoutExpired:compositor.kill();compositor.wait()
