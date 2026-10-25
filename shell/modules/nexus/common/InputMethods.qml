pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import Hyprstack.Config
import Hyprstack.I18n
import qs.components
import qs.components.controls
import qs.services
SettingsCard {
 id:root
 objectName:"desktopInputMethods"
 title:Tr.tr("Input methods");icon:"language";collapsible:true;expanded:false
 property var state:({})
 property string group:""
 property string filter:""
 property DesktopBackend backend:DesktopBackend{}
 function refresh():void {backend.call("input.status",group?{group}: {},value=>{if(!value.error){root.state=value;root.group=value.group??"";}});}
 function act(op,args):void {backend.call(op,args,()=>root.refresh());}
 onExpandedChanged:if(expanded)refresh()
 RowButton {visible:!root.state.running;text:Tr.tr("Enable input method service");icon:"play_arrow";onClicked:root.act("input.enable",{})}
 ToggleRow {text:Tr.tr("Start input methods after login");checked:root.state.startAtLogin??false;onToggled:root.act("input.preferences",{startAtLogin:checked})}
 InfoRow {label:Tr.tr("Active input group");value:root.state.currentGroup??Tr.tr("Not running")}
 Repeater {model:root.state.groups??[];RowButton {required property string modelData;text:modelData;icon:root.group===modelData?"check_circle":"language";onClicked:{root.group=modelData;root.refresh();}}}
 TextFieldRow {id:newGroup;label:Tr.tr("New language group");onValueEdited:value=>newGroup.value=value}
 RowButton {text:Tr.tr("Create language group");icon:"add";disabled:!newGroup.value||root.backend.busy;onClicked:root.act("input.group-create",{group:newGroup.value})}
 RowButton {visible:!!root.group;text:Tr.tr("Use this group");icon:"check";onClicked:root.act("input.group-activate",{group:root.group})}
 RowButton {visible:!!root.group;text:Tr.tr("Remove this group");icon:"delete";disabled:(root.state.groups??[]).length<2;onClicked:root.act("input.group-remove",{group:root.group})}
 TextFieldRow {label:Tr.tr("Default keyboard layout");value:root.state.layout??"";onEditingFinished:value=>root.act("input.group-save",{group:root.group,layout:value,entries:root.state.entries})}
 Repeater {
  model:root.state.entries??[]
  ColumnLayout {
   required property var modelData
   required property int index
   Layout.fillWidth:true
   RowLayout {Layout.fillWidth:true
    RowButton {Layout.fillWidth:true;text:modelData.id;icon:"keyboard";onClicked:root.act("input.method-select",{id:modelData.id})}
    IconButton {icon:"arrow_upward";enabled:index>0;onClicked:{const entries=root.state.entries.slice();[entries[index-1],entries[index]]=[entries[index],entries[index-1]];root.act("input.group-save",{group:root.group,layout:root.state.layout,entries});}}
    IconButton {icon:"arrow_downward";enabled:index<root.state.entries.length-1;onClicked:{const entries=root.state.entries.slice();[entries[index+1],entries[index]]=[entries[index],entries[index+1]];root.act("input.group-save",{group:root.group,layout:root.state.layout,entries});}}
   }
   TextFieldRow {label:Tr.tr("Layout override");value:modelData.layout;onEditingFinished:value=>{const entries=root.state.entries.slice();entries[index]=Object.assign({},modelData,{layout:value});root.act("input.group-save",{group:root.group,layout:root.state.layout,entries});}}
  }
 }
 TextFieldRow {label:Tr.tr("Find an installed input method");value:root.filter;onValueEdited:value=>root.filter=value}
 Repeater {
  model:(root.state.methods??[]).filter(method=>!root.filter||`${method.name} ${method.nativeName} ${method.language}`.toLowerCase().includes(root.filter.toLowerCase())).slice(0,60)
  ToggleRow {required property var modelData;text:modelData.nativeName||modelData.name;subtext:modelData.language;checked:(root.state.entries??[]).some(entry=>entry.id===modelData.id);onToggled:{let entries=(root.state.entries??[]).filter(entry=>entry.id!==modelData.id);if(checked)entries.push({id:modelData.id,layout:""});root.act("input.group-save",{group:root.group,layout:root.state.layout,entries});}}
 }
 RowButton {text:Tr.tr("Advanced input method configuration");icon:"tune";onClicked:root.backend.call("input.configure",{})}
 RowButton {text:Tr.tr("Show on-screen keyboard");icon:"keyboard";onClicked:root.backend.call("input.osk",{visible:true})}
 RowButton {text:Tr.tr("Hide on-screen keyboard");icon:"keyboard_hide";onClicked:root.backend.call("input.osk",{visible:false})}
 FeatureError {error:root.backend.error}
}
