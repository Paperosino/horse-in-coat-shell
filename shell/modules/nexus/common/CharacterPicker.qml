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
 objectName:"desktopCharacterPicker"
 title:Tr.tr("Emoji and special characters");icon:"mood";collapsible:true;expanded:false
 property string query:""
 property string category:"emoji"
 property var items:[]
 property string copied:""
 property DesktopBackend backend:DesktopBackend{}
 function refresh():void {backend.call("input.symbols",{query,category},value=>root.items=value.items??[]);}
 onExpandedChanged:if(expanded)refresh()
 TextFieldRow {label:Tr.tr("Search by name or Unicode code");placeholderText:"HEART / U+1F600";value:root.query;onValueEdited:value=>{root.query=value;delay.restart();}}
 Flow {Layout.fillWidth:true;spacing:Tokens.spacing.small;Repeater {model:[{id:"emoji",label:"Emoji"},{id:"symbols",label:"Symbols"},{id:"latin",label:"Letters"},{id:"all",label:"All"},{id:"recent",label:"Recent"},{id:"favourites",label:"Favourites"}];TextButton {required property var modelData;text:Tr.tr(modelData.label);onClicked:{root.category=modelData.id;root.refresh();}}}}
 Flow {
  Layout.fillWidth:true;spacing:Tokens.spacing.small
  Repeater {model:root.items;TextButton {required property var modelData;text:modelData.text;Accessible.name:modelData.name??modelData.text;onClicked:root.backend.call("input.copy",{text:modelData.text},value=>{if(!value.error)root.copied=modelData.text;});TapHandler {acceptedButtons:Qt.RightButton;onTapped:root.backend.call("input.favourite",{text:parent.modelData.text,enabled:root.category!=="favourites"},()=>root.refresh())}}}
 }
 InfoRow {visible:!!root.copied;label:Tr.tr("Copied");value:root.copied}
 InfoRow {label:Tr.tr("Favourites");value:Tr.tr("Right-click a character to add or remove it from favourites. Characters are copied so you can paste into the intended application.")}
 FeatureError {error:root.backend.error}
 Timer {id:delay;interval:180;onTriggered:root.refresh()}
}
