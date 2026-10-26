pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import Quickshell.Io
import QtQuick.Dialogs
import Hyprstack.Config
import Hyprstack.I18n
import qs.components
import qs.components.controls
import qs.services
import qs.utils
import qs.modules.nexus.common
PageBase {
 id:root
 property bool profilesOnly:false
 title:Tr.tr(profilesOnly?"Desktop profiles":"Configuration history")
 pageIcon:profilesOnly?"style":"history"
 property string selected:""
 property var sections:[]
 property bool importing:false
 property string recoveryError:""
 readonly property var recoveryHelper: Process {
  command:["python3",Paths.toLocalFile(Qt.resolvedUrl("../../../assets/shell_recovery.py")),"on"]
  stdout:StdioCollector {onStreamFinished:{try{root.recoveryError=JSON.parse(text).error??"";}catch(e){root.recoveryError=Tr.tr("Unable to enter safe mode");}}}
 }
 readonly property FileDialog file:FileDialog {fileMode:root.importing?FileDialog.OpenFile:FileDialog.SaveFile;nameFilters:["hics profile (*.json)"];onAccepted:DesktopConfiguration.call(root.importing?"inspect-import":"export-profile",{id:root.selected,path:Paths.toLocalFile(selectedFile)})}
 function inspect(id:string):void {importing=false;selected=id;DesktopConfiguration.call(profilesOnly?"inspect-profile":"inspect-history",{id:id});}
 readonly property Connections previewChange:Connections {target:DesktopConfiguration;function onPreviewChanged():void {root.sections=DesktopConfiguration.preview.files??[];}}
 Component.onCompleted:DesktopConfiguration.refresh()
 ColumnLayout {
  width:root.cappedWidth;anchors.horizontalCenter:parent.horizontalCenter;spacing:Tokens.spacing.medium
  FeatureError {error:DesktopConfiguration.error}
  FeatureError {error:DesktopConfiguration.data.recoveryWarning || ""}
  SettingsCard {
   visible:!root.profilesOnly
   title:Tr.tr("Startup protection");icon:"health_and_safety"
   description:Tr.tr("A separate recovery interface can start even when the normal shell fails. Restoring a startup checkpoint uses a timed preview.")
   RowButton {text:Tr.tr("Mark current startup settings as working");icon:"verified";disabled:DesktopConfiguration.busy||!!DesktopConfiguration.pending;onClicked:DesktopConfiguration.call("mark-startup")}
   RowButton {text:Tr.tr("Try working startup settings");icon:"restore";disabled:DesktopConfiguration.busy||!!DesktopConfiguration.pending||!DesktopConfiguration.data.startupCheckpoint?.available;onClicked:DesktopConfiguration.call("restore-startup")}
   RowButton {text:Tr.tr("Enter safe mode");icon:"shield";subtext:Tr.tr("Restarts only the shell; applications remain open");onClicked:root.recoveryHelper.running=true}
   FeatureError {error:root.recoveryError}
  }
  SettingsCard {
   title:Tr.tr(root.profilesOnly?"Your whole desktop, together":"A way back from every change")
   description:Tr.tr(root.profilesOnly?"Panels, dock, widgets, typography, colours, wallpapers and window mode travel together. Try a profile before keeping it.":"Automatic checkpoints record configuration changes without clipboard contents or assistant credentials. Restore only the sections you need.")
   icon:root.pageIcon
   TextFieldRow {id:name;label:Tr.tr("Name");value:""}
   RowButton {text:Tr.tr(root.profilesOnly?"Save desktop profile":"Create checkpoint");icon:"add";disabled:DesktopConfiguration.busy||!!DesktopConfiguration.pending;onClicked:DesktopConfiguration.call(root.profilesOnly?"save-profile":"snapshot",{name:name.field.text||new Date().toLocaleString()})}
   RowButton {visible:root.profilesOnly;text:Tr.tr("Import desktop profile");icon:"file_open";onClicked:{root.importing=true;root.selected="";file.open();}}
  }
  SettingsCard {
   visible:root.profilesOnly;title:Tr.tr("Starting points");icon:"auto_awesome"
   GridLayout {
    Layout.fillWidth:true;columns:width>550*Tokens.scale?2:1
    Repeater {model:DesktopConfiguration.data.presets??[];RowButton {required property var modelData;text:Tr.tr(modelData.name);subtext:Tr.tr(modelData.description);icon:"desktop_windows";disabled:!!DesktopConfiguration.pending;onClicked:DesktopConfiguration.call("preset",{id:modelData.id})}}
   }
  }
  SettingsCard {
   title:Tr.tr(root.profilesOnly?"Saved profiles":"Checkpoints");icon:"inventory_2"
   Repeater {
    model:root.profilesOnly?(DesktopConfiguration.data.profiles??[]):(DesktopConfiguration.data.history??[])
    RowButton {required property var modelData;text:Tr.tr(modelData.name);subtext:new Date(modelData.created*1000).toLocaleString()+" · "+(modelData.sections??[]).length;icon:"bookmark";trailingIcon:root.selected===modelData.id?"check":"chevron_right";onClicked:root.inspect(modelData.id)}
   }
  }
  SettingsCard {
   visible:!!root.selected||root.importing&&!!DesktopConfiguration.preview.files
   title:Tr.tr("Review what changes");description:DesktopConfiguration.preview.name??"";icon:"preview"
   Repeater {model:DesktopConfiguration.preview.sections??[];ToggleRow {required property var modelData;text:modelData.section;subtext:(modelData.keys??[]).join(", ");checked:root.sections.includes(modelData.section);onToggled:root.sections=checked?[...root.sections,modelData.section]:root.sections.filter(s=>s!==modelData.section)}}
   RowButton {text:Tr.tr(root.importing?"Import reviewed profile":"Try selected sections");icon:"play_arrow";disabled:DesktopConfiguration.busy||!!DesktopConfiguration.pending||!root.sections.length;onClicked:DesktopConfiguration.call(root.importing?"import-profile":root.profilesOnly?"preview-profile":"restore-history",{id:root.selected,path:Paths.toLocalFile(file.selectedFile),sections:root.sections},d=>{if(d.importedId){root.importing=false;root.inspect(d.importedId);}})}
   RowButton {visible:root.profilesOnly&&!!root.selected;text:Tr.tr("Export desktop profile");icon:"file_save";onClicked:{root.importing=false;file.open();}}
   RowButton {visible:!!root.selected;text:Tr.tr("Delete selected item");icon:"delete";onClicked:{DesktopConfiguration.call(root.profilesOnly?"delete-profile":"delete-history",{id:root.selected});root.selected="";}}
  }
  SettingsCard {
   visible:!root.profilesOnly;title:Tr.tr("History policy");icon:"manage_history";collapsible:true;expanded:false
   ToggleRow {text:Tr.tr("Automatic configuration checkpoints");checked:DesktopConfiguration.data.settings?.enabled??true;onToggled:DesktopConfiguration.call("configure",{enabled:checked})}
   ToggleRow {text:Tr.tr("Capture a checkpoint when signing in");checked:DesktopConfiguration.data.settings?.captureOnLogin??true;onToggled:DesktopConfiguration.call("configure",{captureOnLogin:checked})}
   StepperRow {label:Tr.tr("Maximum checkpoints");from:5;to:200;value:DesktopConfiguration.data.settings?.keep??40;onMoved:value=>DesktopConfiguration.call("configure",{keep:value})}
   StepperRow {label:Tr.tr("Maximum history size (MiB)");from:8;to:256;value:DesktopConfiguration.data.settings?.maxMiB??64;onMoved:value=>DesktopConfiguration.call("configure",{maxMiB:value})}
  }
 }
}
