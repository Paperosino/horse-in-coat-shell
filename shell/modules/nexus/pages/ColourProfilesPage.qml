pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import QtQuick.Dialogs
import Hyprstack.Config
import Hyprstack.I18n
import qs.components
import qs.services
import qs.utils
import qs.modules.nexus.common
PageBase {
 id:root
 title:Tr.tr("Display colour profiles");pageIcon:"palette"
 property var state:({})
 property string output:""
 property string profile:""
 property bool confirming:false
 property DesktopBackend backend:DesktopBackend {}
 property FileDialog picker:FileDialog {title:Tr.tr("Import a display ICC profile");nameFilters:["ICC (*.icc *.icm)"];onAccepted:root.backend.call("colour.import",{path:Paths.toLocalFile(selectedFile)},value=>{if(!value.error){root.profile=value.path;root.refresh();}})}
 function refresh():void {backend.call("colour.status",{},value=>{if(!value.error){root.state=value;if(!root.output){root.output=value.monitors?.[0]?.name??"";root.profile=value.assignments?.[root.output]??"";}}});}
 function assign():void {backend.call("colour.assign",{output:root.output,path:root.profile},value=>{root.confirming=false;if(!value.error)root.refresh();});}
 Component.onCompleted:refresh()
 ColumnLayout {
  width:root.cappedWidth;anchors.horizontalCenter:parent.horizontalCenter;spacing:Tokens.spacing.large
  SettingsCard {
   title:Tr.tr("Colour accuracy for your display");icon:"palette"
   description:Tr.tr("Use a display-specific RGB ICC profile from your manufacturer or calibration tool. Hyprland applies it to the selected output; an ICC profile overrides its colour preset and is incompatible with HDR gaming.")
   RowButton {text:Tr.tr("Refresh monitors and profiles");icon:"refresh";disabled:root.backend.busy;onClicked:root.refresh()}
   GenericSettingRow {spec:({label:"Monitor",type:"choice",choices:(root.state.monitors??[]).map(m=>({value:m.name,label:m.description||m.name})),value:root.output});onEdited:value=>{root.output=value;root.profile=root.state.assignments?.[value]??"";root.confirming=false;}}
   GenericSettingRow {spec:({label:"ICC profile",type:"choice",choices:[{value:"",label:"No ICC override"},...(root.state.profiles??[]).map(p=>({value:p.path,label:p.name}))],value:root.profile});onEdited:value=>{root.profile=value;root.confirming=false;}}
   InfoRow {label:Tr.tr("Current hics assignment");value:root.state.assignments?.[root.output]||Tr.tr("No ICC override")}
   RowButton {text:Tr.tr("Import a display ICC profile");icon:"file_open";disabled:root.backend.busy;onClicked:root.picker.open()}
   RowButton {text:root.confirming?Tr.tr("Confirm colour profile change"):Tr.tr("Apply to this monitor");icon:"check";disabled:root.backend.busy||!root.output;onClicked:{if(!root.confirming){root.confirming=true;return;}root.assign();}}
   RowButton {text:Tr.tr("Remove the ICC override");icon:"restart_alt";disabled:root.backend.busy||!root.output;onClicked:{root.profile="";root.confirming=true;}}
  }
  SettingsCard {
   title:"colord";icon:"colorize";collapsible:true;expanded:false
   description:Tr.tr("Installed display profiles are read from colord. Imported files are copied to your user ICC directory; printer and scanner profiles are excluded.")
   InfoRow {label:Tr.tr("System colour service");value:root.state.colord?Tr.tr("Available"):Tr.tr("Unavailable; user profiles still work")}
  }
  FeatureError {error:root.backend.error}
 }
}
