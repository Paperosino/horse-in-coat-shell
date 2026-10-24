pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import Hyprstack.Config
import Hyprstack.I18n
import qs.components
import qs.components.controls
import qs.services
import qs.modules.nexus.common
PageBase {
 id:root;title:Tr.tr("Settings workbench");pageIcon:"tune"
 property var rows:[]
 property int limit:40
 property string query:""
 property bool changedOnly:true
 property string section:""
 function refresh():void {rows=GlobalConfig.settingsRows();}
 Component.onCompleted:refresh()
 ColumnLayout {
  width:root.cappedWidth;anchors.horizontalCenter:parent.horizontalCenter;spacing:Tokens.spacing.medium
  SettingsCard {
   title:Tr.tr("Every setting has a way back");description:Tr.tr("Inspect effective values, defaults and explicit overrides. Reset a single setting or its entire section using the same native schema as the shell.");icon:"settings_backup_restore"
   TextFieldRow {label:Tr.tr("Find a setting");value:root.query;onValueEdited:value=>root.query=value}
   ToggleRow {text:Tr.tr("Show changed settings only");checked:root.changedOnly;onToggled:root.changedOnly=checked}
   GenericSettingRow {spec:({label:"Section",type:"choice",choices:["",...new Set(root.rows.map(r=>r.path.split('.')[0]))]});value:root.section;onEdited:value=>root.section=value}
   RowButton {text:Tr.tr("Refresh values");icon:"refresh";onClicked:root.refresh()}
   RowButton {visible:!!root.section;text:Tr.tr("Reset this section");icon:"restart_alt";onClicked:{GlobalConfig.resetSetting(root.section);Qt.callLater(root.refresh);}}
  }
  RowButton {text:Tr.tr("Show more settings");icon:"expand_more";onClicked:root.limit+=40}
  Repeater {
   model:root.rows.filter(r=>(!root.changedOnly||r.overridden)&&(!root.section||r.path.startsWith(root.section+"."))&&(!root.query||r.path.toLowerCase().includes(root.query.toLowerCase()))).slice(0,root.limit)
   SettingsCard {
    id:entry;required property var modelData
    title:modelData.path;icon:modelData.overridden?"edit":"settings";badge:modelData.overridden?Tr.tr("Changed"):""
    InfoRow {label:Tr.tr("Current value");value:JSON.stringify(entry.modelData.value)}
    InfoRow {label:Tr.tr("Default value");value:JSON.stringify(entry.modelData.default??null)}
    GenericSettingRow {visible:["bool","int","double","float","QString","string"].includes(entry.modelData.type);spec:({label:"Value",type:entry.modelData.type==="bool"?"bool":["int","double","float"].includes(entry.modelData.type)?"number":"string",value:entry.modelData.value});onEdited:value=>{const num=["int","double","float"].includes(entry.modelData.type)?Number(value):value;if(GlobalConfig.editSetting(entry.modelData.path,num))Qt.callLater(root.refresh);}}
    RowButton {text:Tr.tr("Reset to default");icon:"restart_alt";onClicked:{GlobalConfig.resetSetting(entry.modelData.path);Qt.callLater(root.refresh);}}
   }
  }
 }
}
