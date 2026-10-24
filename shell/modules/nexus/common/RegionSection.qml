pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import Hyprstack.Config
import Hyprstack.I18n
import qs.components
import qs.components.controls
import qs.services
ColumnLayout {
 id:root
 property string selected:""
 property string query:""
 property bool allFormats:true
 readonly property bool busy:system.busy
 signal applied()
 function applySelected():void {if(selected)system.apply("locale",{locale:selected,allFormats:allFormats});}
 Layout.fillWidth:true
 NativeSystemBackend {id:system;section:"region";onApplied:{root.selected="";root.applied();}}
 SettingsCard {
  title:Tr.tr("System locale");description:Tr.tr("Set the language and regional formats for the system. Locale generation is handled by the system service with authorization.");icon:"public"
  FeatureError {error:system.error}
  InfoRow {label:Tr.tr("Current system locale");value:(system.state.current??[]).join(" · ")}
  TextFieldRow {label:Tr.tr("Find a locale");value:root.query;placeholderText:"ru_RU · English · Deutsch";onValueEdited:v=>root.query=v}
  GenericSettingRow {spec:({label:"System locale",type:"choice",choices:(system.state.locales??[]).filter(l=>!root.query||l.id.toLowerCase().includes(root.query.toLowerCase())||l.name.toLowerCase().includes(root.query.toLowerCase())).slice(0,80).map(l=>({value:l.id,label:l.name})),value:root.selected});onEdited:v=>root.selected=v}
  ToggleRow {text:Tr.tr("Use the same locale for dates and numbers");checked:root.allFormats;onToggled:root.allFormats=checked}
  RowButton {text:system.busy?Tr.tr("Generating locale…"):Tr.tr("Apply system locale");icon:"language";disabled:system.busy||!root.selected;onClicked:root.applySelected()}
 }
}
