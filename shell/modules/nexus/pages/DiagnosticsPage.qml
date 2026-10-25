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
 id:root;title:Tr.tr("Desktop health");pageIcon:"monitor_heart"
 property var report:({checks:[]})
 property string scenario:"all"
 property string confirm:""
 property DesktopBackend backend:DesktopBackend{}
 property FeatureBackend legacy:FeatureBackend {helper:"desktop_diagnostics.py"}
 property var units:[]
 readonly property FileDialog exporter:FileDialog {fileMode:FileDialog.SaveFile;defaultSuffix:"json";nameFilters:["hics report (*.json)"];onAccepted:root.backend.call("diagnostics.export",{path:Paths.toLocalFile(selectedFile)})}
 function check():void {backend.call("diagnostics.check",{},value=>{if(!value.error)root.report=value;});}
 function repair(id:string):void {backend.call("diagnostics.repair",{id},()=>root.check());confirm="";}
 ColumnLayout {
  width:root.cappedWidth;anchors.horizontalCenter:parent.horizontalCenter;spacing:Tokens.spacing.large
  SettingsCard {
   title:Tr.tr("What is not working?");icon:"healing"
   description:Tr.tr("Choose a problem, run checks and follow concrete steps. The report includes only named checks and numeric states; passwords, tokens, connection names and raw logs are excluded.")
   Repeater {model:[{id:"sound",label:"No sound or microphone"},{id:"network",label:"No internet"},{id:"sharing",label:"Screen sharing does not work"},{id:"all",label:"Check everything"}];RowButton {required property var modelData;text:Tr.tr(modelData.label);icon:root.scenario===modelData.id?"check_circle":"troubleshoot";onClicked:{root.scenario=modelData.id;root.check();}}}
   RowButton {text:Tr.tr("Run checks");icon:"refresh";disabled:root.backend.busy;onClicked:root.check()}
   RowButton {text:Tr.tr("Save diagnostic report");icon:"file_save";disabled:root.backend.busy||!(root.report.checks??[]).length;onClicked:root.exporter.open()}
   FeatureError {error:root.backend.error}
  }
  Repeater {
   model:(root.report.checks??[]).filter(check=>root.scenario==="all"||root.scenario==="sound"&&["output","microphone"].includes(check.id)||root.scenario==="network"&&["network","internet"].includes(check.id)||root.scenario==="sharing"&&check.id.startsWith("portal"))
   SettingsCard {required property var modelData;title:Tr.tr(modelData.name);icon:modelData.ok?"task_alt":"error";badge:modelData.ok?Tr.tr("Ready"):Tr.tr("Needs attention");InfoRow {label:Tr.tr("Next step");value:Tr.tr(modelData.action)}}
  }
  SettingsCard {
   title:Tr.tr("Try a repair");icon:"build"
   RowButton {visible:root.scenario==="all"||root.scenario==="sound";text:Tr.tr("Unmute audio output");icon:"volume_up";disabled:root.backend.busy;onClicked:root.repair("audio-output")}
   RowButton {visible:root.scenario==="all"||root.scenario==="sound";text:root.confirm==="audio-service"?Tr.tr("Confirm audio service restart"):Tr.tr("Restart audio services");subtext:Tr.tr("Active audio and microphone streams will be interrupted");icon:"restart_alt";disabled:root.backend.busy;onClicked:{if(root.confirm==="audio-service")root.repair("audio-service");else root.confirm="audio-service";}}
   RowButton {visible:root.scenario==="all"||root.scenario==="network";text:Tr.tr("Recheck internet connectivity");icon:"wifi_find";disabled:root.backend.busy;onClicked:root.repair("internet-check")}
   RowButton {visible:root.scenario==="all"||root.scenario==="sharing";text:root.confirm==="screen-sharing"?Tr.tr("Confirm sharing portal restart"):Tr.tr("Restart sharing portals");subtext:Tr.tr("Active screen sharing will stop");icon:"restart_alt";disabled:root.backend.busy;onClicked:{if(root.confirm==="screen-sharing")root.repair("screen-sharing");else root.confirm="screen-sharing";}}
   RowButton {text:Tr.tr("Open relevant settings");icon:"settings";onClicked:root.nState.openPage(root.scenario==="network"?"network":root.scenario==="sharing"?"sharing":"audio")}
  }
  SettingsCard {
   title:Tr.tr("Advanced service recovery");icon:"settings_suggest";collapsible:true;expanded:false
   RowButton {text:Tr.tr("Inspect desktop services");icon:"refresh";onClicked:root.legacy.call(["status"],null,value=>root.units=value.units??[])}
   Repeater {model:root.units;RowButton {required property var modelData;text:modelData.id;subtext:(modelData.ActiveState??"unknown")+" · "+(modelData.SubState??"");icon:"restart_alt";disabled:root.legacy.busy;onClicked:root.legacy.call(["restart"],{unit:modelData.id,logs:false},value=>root.units=value.units??[])}}
   FeatureError {error:root.legacy.error}
  }
 }
}
