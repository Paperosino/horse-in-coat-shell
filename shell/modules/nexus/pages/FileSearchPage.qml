pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import QtQuick.Dialogs
import qs.utils
import Quickshell
import Hyprstack.Config
import Hyprstack.I18n
import qs.components
import qs.components.controls
import qs.services
import qs.modules.nexus.common
PageBase {
 id:root
 title:Tr.tr("File search");pageIcon:"manage_search"
 property var prefs:({})
 property var results:[]
 property string query:""
 property FolderDialog folderPicker:FolderDialog {onAccepted:root.save({folders:[...(root.prefs.folders??[]),Paths.toLocalFile(selectedFolder)]})}
 property FolderDialog excludePicker:FolderDialog {onAccepted:root.save({excluded:[...(root.prefs.excluded??[]),Paths.toLocalFile(selectedFolder)]})}

 property string summary:""
 property DesktopBackend backend:DesktopBackend{}
 Component.onCompleted:backend.call("search.config",{},value=>root.prefs=value)
 function save(change):void {backend.call("search.configure",change,value=>{if(!value.error){root.prefs=value;root.results=[];}});}
 ColumnLayout {
  width:root.cappedWidth;anchors.horizontalCenter:parent.horizontalCenter;spacing:Tokens.spacing.large
  SettingsCard {
   title:Tr.tr("Private, bounded indexing");icon:"manage_search"
   description:Tr.tr("In the application menu, type the action prefix followed by files and a search query. Indexes selected folders without following symbolic links or entering hidden folders. Each run is limited to ten seconds; text extraction is limited to 8 MiB.")
   RowButton {text:Tr.tr("Add a search folder");icon:"create_new_folder";onClicked:root.folderPicker.open()}
   Repeater {model:root.prefs.folders??[];RowLayout {required property string modelData;Layout.fillWidth:true;MaterialIcon {text:"folder";color:Colours.palette.m3primary}StyledText {Layout.fillWidth:true;text:modelData;wrapMode:Text.WrapAnywhere;textFormat:Text.PlainText}IconButton {icon:"close";onClicked:root.save({folders:root.prefs.folders.filter(path=>path!==modelData)})}}}
   RowButton {text:Tr.tr("Exclude a private folder");icon:"folder_off";onClicked:root.excludePicker.open()}
   Repeater {model:root.prefs.excluded??[];RowLayout {required property string modelData;Layout.fillWidth:true;MaterialIcon {text:"folder_off";color:Colours.palette.m3onSurfaceVariant}StyledText {Layout.fillWidth:true;text:modelData;wrapMode:Text.WrapAnywhere;textFormat:Text.PlainText}IconButton {icon:"close";onClicked:root.save({excluded:root.prefs.excluded.filter(path=>path!==modelData)})}}}
   ToggleRow {text:Tr.tr("Index text contents");checked:root.prefs.contents??false;onToggled:root.save({contents:checked})}
   ToggleRow {text:Tr.tr("Extract PDF text");subtext:Tr.tr("Up to five pages per file and four changed PDFs per run");checked:root.prefs.pdf??false;onToggled:root.save({pdf:checked})}
   ToggleRow {text:Tr.tr("Automatically refresh the index");checked:root.prefs.automatic??false;onToggled:root.save({automatic:checked})}
   ToggleRow {text:Tr.tr("Pause automatic indexing on battery");checked:root.prefs.pauseOnBattery??true;onToggled:root.save({pauseOnBattery:checked})}
   ToggleRow {text:Tr.tr("Pause automatic indexing during games");checked:root.prefs.pauseForGames??true;onToggled:root.save({pauseForGames:checked})}
   StepperRow {label:Tr.tr("Index refresh interval (minutes)");from:1;to:1440;stepSize:5;value:root.prefs.intervalMinutes??15;onMoved:value=>root.save({intervalMinutes:value})}
   StepperRow {label:Tr.tr("Time budget per run (milliseconds)");from:100;to:10000;stepSize:100;value:root.prefs.budgetMs??10000;onMoved:value=>root.save({budgetMs:value})}
   StepperRow {label:Tr.tr("Maximum indexed files");from:100;to:50000;stepSize:100;value:root.prefs.maxFiles??10000;onMoved:value=>root.save({maxFiles:value})}
   StepperRow {label:Tr.tr("Maximum content size (MiB)");from:1;to:64;stepSize:1;value:root.prefs.contentMiB??8;onMoved:value=>root.save({contentMiB:value})}
   StepperRow {label:Tr.tr("Pause above CPU load (%)");from:10;to:95;stepSize:5;value:root.prefs.maxCpuLoadPercent??70;onMoved:value=>root.save({maxCpuLoadPercent:value})}
   RowButton {text:Tr.tr("Build index now");icon:"refresh";disabled:root.backend.busy;onClicked:root.backend.call("search.index",{},value=>root.summary=value.error??Tr.tr("Indexed %1 files").arg(value.count??0)+(value.limited?" · "+Tr.tr("Limit reached"):""))}
   RowButton {text:Tr.tr("Erase index");icon:"delete";disabled:root.backend.busy;onClicked:root.backend.call("search.clear",{},()=>root.results=[])}
   InfoRow {visible:!!root.summary;label:Tr.tr("Last run");value:root.summary}
   FeatureError {error:root.backend.error}
  }
  SettingsCard {
   title:Tr.tr("Find a document");icon:"search"
   TextFieldRow {label:Tr.tr("Words or filename");value:root.query;onValueEdited:value=>root.query=value}
   RowButton {text:Tr.tr("Search");icon:"search";disabled:root.backend.busy||!root.query;onClicked:root.backend.call("search.query",{query:root.query},value=>root.results=value.items??[])}
   Repeater {model:root.results;RowButton {required property var modelData;text:modelData.name;subtext:modelData.path;icon:"description";onClicked:Quickshell.execDetached(["gio","open",modelData.path])}}
  }
 }
}
