pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import QtQuick.Dialogs
import qs.utils
import Hyprstack.Config
import Hyprstack.I18n
import qs.components
import qs.components.controls
import qs.services
import qs.modules.nexus.common
PageBase {
 id:root
 title:Tr.tr("Backups");pageIcon:"backup"
 property var prefs:({})
 property var snapshots:[]
 property var files:[]
 property bool listLimited:false
 property string browseFolder:"/"
 property string selectedFile:""
 property FolderDialog sourcePicker:FolderDialog {onAccepted:{const path=Paths.toLocalFile(selectedFolder);const folders=root.folders.slice();if(!folders.includes(path))folders.push(path);root.folders=folders;}}
 property FolderDialog repositoryPicker:FolderDialog {onAccepted:root.repository=Paths.toLocalFile(selectedFolder)+"/hics-backups"}
 property FolderDialog restorePicker:FolderDialog {onAccepted:root.target=Paths.toLocalFile(selectedFolder)+"/hics-restored-"+Date.now()}
 function listFiles():void {backend.call("backup.files",{snapshot:selected,folder:browseFolder},value=>{root.files=value.items??[];root.listLimited=value.limited??false;});}
 function save():void {backend.call("backup.configure",Object.assign({},prefs,{repository,folders,password:password.text,intervalHours}),value=>{if(!value.error)root.prefs=value;});password.clear();}
 function preference(key,value):void {prefs=Object.assign({},prefs,{[key]:value});}

 property string repository:""
 property var folders:[]
 property int intervalHours:0
 property string target:""
 property string selected:""
 property DesktopBackend backend:DesktopBackend{}
 Component.onCompleted:backend.call("backup.config",{},value=>{root.prefs=value;root.repository=value.repository??"";root.folders=value.folders??[];root.intervalHours=value.intervalHours??0;})
 ColumnLayout {
  width:root.cappedWidth;anchors.horizontalCenter:parent.horizontalCenter;spacing:Tokens.spacing.large
  SettingsCard {
   title:Tr.tr("Encrypted personal backups");icon:"backup"
   description:Tr.tr("Restic stores encrypted snapshots. The repository password is stored in your existing keyring. Keep a recovery copy: losing that password makes the backups unreadable.")
   RowButton {text:Tr.tr("Choose a backup disk or folder");icon:"hard_drive";onClicked:root.repositoryPicker.open()}
   RowButton {text:Tr.tr("Add a folder to back up");icon:"create_new_folder";onClicked:root.sourcePicker.open()}
   TextFieldRow {label:Tr.tr("Repository folder");value:root.repository;onValueEdited:value=>root.repository=value}
   Repeater {model:root.folders;RowLayout {required property string modelData;Layout.fillWidth:true;MaterialIcon {text:"folder";color:Colours.palette.m3primary}StyledText {Layout.fillWidth:true;text:modelData;wrapMode:Text.WrapAnywhere;textFormat:Text.PlainText}IconButton {icon:"close";onClicked:root.folders=root.folders.filter(path=>path!==modelData)}}}

   TextFieldRow {label:Tr.tr("Backup interval in hours");subtext:Tr.tr("0 disables scheduling; between 1 and 168 hours");value:String(root.intervalHours);onEditingFinished:value=>root.intervalHours=Math.max(0,Math.min(168,parseInt(value)||0))}
   StyledTextField {id:password;Layout.fillWidth:true;placeholderText:Tr.tr("Repository password (leave blank to keep saved password)");echoMode:TextInput.Password;maximumLength:1024}
   RowButton {text:Tr.tr("Save configuration");icon:"save";disabled:root.backend.busy;onClicked:root.save()}
   TextFieldRow {label:Tr.tr("Excluded paths or patterns");value:(root.prefs.excluded??[]).join("; ");onEditingFinished:value=>root.preference("excluded",value.split(";").map(v=>v.trim()).filter(v=>v))}
   ToggleRow {text:Tr.tr("Exclude marked cache folders");checked:root.prefs.excludeCaches??true;onToggled:root.preference("excludeCaches",checked)}
   ToggleRow {text:Tr.tr("Stay within each source filesystem");checked:root.prefs.oneFileSystem??false;onToggled:root.preference("oneFileSystem",checked)}
   TextFieldRow {label:Tr.tr("Compression mode");subtext:"auto / off / fastest / better / max";value:root.prefs.compression??"auto";onEditingFinished:value=>root.preference("compression",value)}
   StepperRow {label:Tr.tr("Transfer limit (KiB/s; 0 is unlimited)");from:0;to:1048576;stepSize:1024;value:root.prefs.limitKiB??0;onMoved:value=>root.preference("limitKiB",value)}
   StepperRow {label:Tr.tr("Minimum free disk space (MiB)");from:0;to:1048576;stepSize:256;value:root.prefs.minFreeMiB??256;onMoved:value=>root.preference("minFreeMiB",value)}
   RowButton {text:Tr.tr("Save advanced backup settings");icon:"save";disabled:root.backend.busy;onClicked:root.save()}
   RowButton {text:Tr.tr("Initialize a new repository");subtext:Tr.tr("Use once for a new, empty repository");icon:"create_new_folder";disabled:root.backend.busy;onClicked:root.backend.call("backup.init",{})}
   RowButton {text:Tr.tr("Back up now");icon:"backup";disabled:root.backend.busy;onClicked:root.backend.call("backup.run",{})}
   RowButton {text:Tr.tr("Check repository integrity");icon:"verified_user";disabled:root.backend.busy;onClicked:root.backend.call("backup.check",{})}
   FeatureError {error:root.backend.error}
  }
  SettingsCard {
   title:Tr.tr("Restore safely");icon:"restore"
   RowButton {text:Tr.tr("Load snapshots");icon:"refresh";disabled:root.backend.busy;onClicked:root.backend.call("backup.snapshots",{},value=>root.snapshots=value.items??[])}
   Repeater {model:root.snapshots;RowButton {required property var modelData;text:modelData.short_id??modelData.id;subtext:modelData.time??"";icon:root.selected===modelData.id?"check_circle":"history";onClicked:{root.selected=modelData.id;root.selectedFile="";root.browseFolder="/";root.listFiles();}}}
   RowButton {visible:!!root.selected;text:Tr.tr("Parent snapshot folder");subtext:root.browseFolder;icon:"drive_folder_upload";onClicked:{root.browseFolder=root.browseFolder.split("/").slice(0,-1).join("/")||"/";root.listFiles();}}
   InfoRow {visible:root.listLimited;label:Tr.tr("List limit");value:Tr.tr("Showing the first 1000 entries. Open a subfolder or enter the file path in the restore filter.")}
   Repeater {model:root.files;RowButton {required property var modelData;text:modelData.name||modelData.path;subtext:modelData.path;icon:modelData.type==="dir"?"folder":root.selectedFile===modelData.path?"check_circle":"description";onClicked:{if(modelData.type==="dir"){root.browseFolder=modelData.path;root.listFiles();}else{root.selectedFile=modelData.path;include.value=modelData.path;}}}}
   RowButton {text:Tr.tr("Choose where to restore");icon:"folder_open";onClicked:root.restorePicker.open()}
   TextFieldRow {label:Tr.tr("Restore to a new folder");value:root.target;onValueEdited:value=>root.target=value}
   TextFieldRow {id:include;label:Tr.tr("File or folder filter (optional)");value:"";onValueEdited:value=>include.value=value}
   RowButton {text:Tr.tr("Restore selected snapshot");subtext:Tr.tr("Existing target directories are refused to protect current files");icon:"restore";disabled:root.backend.busy||!root.selected||!root.target;onClicked:root.backend.call("backup.restore",{snapshot:root.selected,target:root.target,include:include.value,literal:root.selectedFile===include.value})}
  }
  SettingsCard {
   title:Tr.tr("System snapshots");icon:"history"
   description:Tr.tr("Timeshift manages system recovery separately from personal files. Its Btrfs mode requires a compatible @ and @home subvolume layout; other layouts can use its rsync mode. A snapshot on the same disk does not protect against disk failure.")
   RowButton {text:Tr.tr("Open existing Snapper snapshots");icon:"history";onClicked:root.backend.call("backup.snapper-manager",{})}
   RowButton {text:Tr.tr("Open Timeshift");icon:"admin_panel_settings";onClicked:root.backend.call("backup.timeshift-manager",{})}
  }
 }
}
