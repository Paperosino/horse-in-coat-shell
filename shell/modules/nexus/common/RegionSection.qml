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
 property int resultLimit:6
 property bool allFormats:true
 property bool succeeded:false
 readonly property string error:system.error
 readonly property bool busy:system.busy
 readonly property string currentLocale:system.state.currentLocale??(system.state.current??[]).find(v=>v.startsWith("LANG="))?.substring(5)??(system.state.available?"C.UTF-8":"")
 readonly property var matches:(system.state.locales??[]).filter(l=>{
  const q=root.query.trim().toLowerCase().replace(/utf[_-]?8/g,"utf8").replace(/-/g,"_");
  if(!q)return l.id===root.selected||l.id===root.currentLocale||["ru_RU","en_US","en_GB","de_DE","fr_FR","es_ES","it_IT","pt_BR"].some(code=>l.id.startsWith(code+"."));
  const aliases={"ru":"русский россия russian","en":"английский english","de":"немецкий deutsch german","fr":"французский french","es":"испанский spanish","uk":"украинский ukrainian","zh":"китайский chinese","ja":"японский japanese"};
  return [l.id,l.name,l.language,l.territory,aliases[l.id.split("_")[0]]??""].join(" ").toLowerCase().replace(/utf[_-]?8/g,"utf8").replace(/-/g,"_").includes(q);
 }).sort((a,b)=>{
  const common=["ru_RU.UTF-8","en_US.UTF-8","en_GB.UTF-8","de_DE.UTF-8","fr_FR.UTF-8","es_ES.UTF-8"];
  function rank(l){return l.id===root.selected?-2:l.id===root.currentLocale?-1:common.includes(l.id)?common.indexOf(l.id):100;}
  return rank(a)-rank(b)||a.id.localeCompare(b.id);
 })
 signal applied()
 function applySelected():void {if(selected&&!busy){succeeded=false;system.apply("locale",{locale:selected,allFormats:allFormats});}}
 onQueryChanged:resultLimit=6
 onSelectedChanged:succeeded=false
 onAllFormatsChanged:succeeded=false
 Layout.fillWidth:true
 NativeSystemBackend {id:system;section:"region";onApplied:{root.succeeded=true;root.applied();}}
 SettingsCard {
  title:Tr.tr("System locale")
  description:Tr.tr("Choose a locale from the search results, then apply it. Existing applications use the new language after signing in again.")
  icon:"public"
  FeatureError {objectName:"locale-error";error:system.error}
  RowButton {visible:!!root.error;text:Tr.tr("Retry");icon:"refresh";disabled:root.busy;onClicked:if(system.state.available&&root.selected)root.applySelected();else system.reload()}
  InfoRow {label:Tr.tr("Current system locale");value:root.currentLocale||(root.error?Tr.tr("Unavailable"):Tr.tr("Loading…"))}
  TextFieldRow {objectName:"locale-search";enabled:!root.busy;label:Tr.tr("Find a locale");value:root.query;placeholderText:"ru_RU · русский · English";onValueEdited:v=>root.query=v}
  StyledText {Layout.fillWidth:true;visible:!root.matches.length&&!system.busy;text:Tr.tr("No matching locales");color:Colours.palette.m3onSurfaceVariant;wrapMode:Text.WordWrap}
  GridLayout {
   Layout.fillWidth:true;columns:width>620*Tokens.scale?2:1
  Repeater {
   model:root.matches.slice(0,root.resultLimit)
   RowButton {
    required property var modelData
    objectName:"locale-choice-"+modelData.id
    disabled:root.busy
    text:modelData.id==="C.UTF-8"?Tr.tr("System default"):modelData.name
    subtext:modelData.id
    trailingIcon:root.selected===modelData.id?"radio_button_checked":"radio_button_unchecked"
    onClicked:root.selected=modelData.id
   }
  }
  }
  RowButton {visible:root.matches.length>root.resultLimit;text:Tr.tr("Show more");icon:"expand_more";onClicked:root.resultLimit+=12}
  InfoRow {objectName:"locale-selection";label:Tr.tr("Selected locale");value:root.selected||Tr.tr("Select a locale")}
  ToggleRow {enabled:!root.busy;text:Tr.tr("Use the same locale for dates and numbers");checked:root.allFormats;onToggled:root.allFormats=checked}
  RowButton {objectName:"locale-apply";text:root.selected&&system.busy?Tr.tr("Applying locale…"):Tr.tr("Apply system locale");icon:"language";disabled:system.busy||!root.selected;onClicked:root.applySelected()}
  StyledText {Layout.fillWidth:true;visible:root.succeeded;text:Tr.tr("System locale applied. New applications use it after your next sign-in.");color:Colours.palette.m3primary;wrapMode:Text.WordWrap}
 }
}
