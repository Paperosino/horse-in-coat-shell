pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import QtQuick.Controls
import QtQuick.Dialogs
import qs.utils
import Hyprstack.Config
import Hyprstack.I18n
import qs.components
import qs.components.controls
import qs.services
ColumnLayout {
 id:root
 objectName:"desktopApplicationPermissions"
 required property var application
 property var details:({})
 property var armor:({})
 property string selectedProfile:""
 property var policy:({})
 property string policyText:""
 property bool folderReadOnly:true
 property FolderDialog folderGrant:FolderDialog {onAccepted:root.backend.call("apps.flatpak-override",{id:root.details.flatpak,options:["--filesystem="+Paths.toLocalFile(selectedFolder)+(root.folderReadOnly?":ro":":rw")]},()=>root.reload())}
 property bool advanced:false
 property DesktopBackend backend:DesktopBackend{}
 Layout.fillWidth:true;spacing:Tokens.spacing.large
 function reload():void {if(!application)return;backend.call("apps.info",{id:application.id,path:application.filePath},value=>{if(!value.error)root.details=value;});}
 onApplicationChanged:reload()
 Component.onCompleted:reload()
 SettingsCard {
  title:Tr.tr("Application access");icon:"shield"
  description:root.details.flatpak?Tr.tr("Per-user Flatpak overrides. Portal permissions and access already granted to running applications may require restarting the application."):Tr.tr("Native applications are not automatically sandboxed. AppArmor only restricts an application with a matching enforced profile.")
  Repeater {
   model:root.details.flatpak?[
    {name:Tr.tr("Network"),group:"shared",flag:"network",yes:"--share=network",no:"--unshare=network"},
    {name:Tr.tr("Audio, including microphone access"),group:"sockets",flag:"pulseaudio",yes:"--socket=pulseaudio",no:"--nosocket=pulseaudio"},
    {name:Tr.tr("GPU acceleration"),group:"devices",flag:"dri",yes:"--device=dri",no:"--nodevice=dri"},
    {name:Tr.tr("All devices (broad access)"),group:"devices",flag:"all",yes:"--device=all",no:"--nodevice=all"},
    {name:Tr.tr("Home folder"),group:"filesystems",flag:"home",yes:"--filesystem=home",no:"--nofilesystem=home"},
    {name:Tr.tr("Wayland"),group:"sockets",flag:"wayland",yes:"--socket=wayland",no:"--nosocket=wayland"},
    {name:Tr.tr("X11 (reduced isolation)"),group:"sockets",flag:"x11",yes:"--socket=x11",no:"--nosocket=x11"}
   ]:[]
   ToggleRow {required property var modelData;first:true;last:true;text:modelData.name;checked:(root.details.permissions?.Context?.[modelData.group]??"").split(";").some(flag=>flag===modelData.flag||flag.startsWith(modelData.flag+":"));enabled:!root.backend.busy;onToggled:root.backend.call("apps.flatpak-override",{id:root.details.flatpak,options:[checked?modelData.yes:modelData.no]},()=>root.reload())}
  }
  ToggleRow {visible:!!root.details.flatpak;text:Tr.tr("Read-only access for new folder grants");checked:root.folderReadOnly;onToggled:root.folderReadOnly=checked}
  RowButton {visible:!!root.details.flatpak;text:Tr.tr("Grant access to a folder");icon:"folder_open";disabled:root.backend.busy;onClicked:root.folderGrant.open()}
  Repeater {model:root.details.flatpak?(root.details.permissions?.Context?.filesystems??"").split(";").filter(scope=>scope&&!scope.startsWith("!")):[];ToggleRow {required property string modelData;text:modelData.replace(/:(ro|rw|create)$/,"" );subtext:modelData.endsWith(":ro")?Tr.tr("Read-only"):Tr.tr("Read and write");checked:true;onToggled:if(!checked)root.backend.call("apps.flatpak-override",{id:root.details.flatpak,options:["--nofilesystem="+modelData.replace(/:(ro|rw|create)$/,"")]},()=>root.reload())}}
  InfoRow {label:Tr.tr("Camera portal");value:Tr.tr("Controls applications that use the camera portal. Direct camera device access bypasses portal grants; microphone permissions depend on the application's audio backend.")}
  Repeater {model:[{id:"yes",name:"Allow camera portal access"},{id:"no",name:"Deny camera portal access"},{id:"ask",name:"Ask again next time"}];RowButton {required property var modelData;text:Tr.tr(modelData.name);icon:"videocam";onClicked:root.backend.call("apps.portal-camera",{id:root.details.flatpak||root.application.id.replace(/\.desktop$/,""),policy:modelData.id})}}
  ToggleRow {first:true;last:true;text:Tr.tr("Launch at login");checked:root.details.autostart??false;onToggled:root.backend.call("apps.autostart",{id:root.application.id,path:root.application.filePath,enabled:checked},value=>{if(!value.error)root.reload();})}
  RowButton {visible:!!root.details.flatpak;first:true;last:true;text:Tr.tr("Restore default Flatpak permissions");icon:"restart_alt";disabled:root.backend.busy;onClicked:root.backend.call("apps.flatpak-reset",{id:root.details.flatpak},()=>root.reload())}
  ToggleRow {visible:!!root.details.flatpak;first:true;last:true;text:Tr.tr("Advanced Flatpak settings");checked:root.advanced;onToggled:root.advanced=checked}
  InfoRow {visible:root.advanced;first:true;last:true;label:Tr.tr("Effective permissions");value:JSON.stringify(root.details.permissions??{},null,2)}
  TextFieldRow {id:override;visible:root.advanced;first:true;last:true;label:Tr.tr("Override option");placeholderText:"--filesystem=xdg-documents:ro";onValueEdited:value=>override.value=value}
  RowButton {visible:root.advanced;text:Tr.tr("Apply override");icon:"tune";disabled:root.backend.busy||!override.value;onClicked:root.backend.call("apps.flatpak-override",{id:root.details.flatpak,options:[override.value]},()=>root.reload())}
  FeatureError {error:root.backend.error}
 }
 SettingsCard {
  title:Tr.tr("AppArmor");icon:"security";collapsible:true;expanded:false
  RowButton {first:true;last:true;text:Tr.tr("Inspect system profiles");icon:"refresh";disabled:root.backend.busy;onClicked:root.backend.call("apps.apparmor-status",{},result=>{if(!result.error)root.armor=result;})}
  InfoRow {first:true;last:true;label:Tr.tr("Kernel enforcement");value:root.armor.apparmorActive?Tr.tr("AppArmor is active"):Tr.tr("AppArmor is unavailable or not enabled in the kernel")}
  ToggleRow {text:Tr.tr("Enable AppArmor at startup");subtext:Tr.tr("System-wide setting; requires AppArmor support in the running kernel");checked:root.armor.apparmorServiceEnabled??false;enabled:!root.backend.busy;onToggled:root.backend.call("apps.apparmor-service",{enabled:checked},value=>root.armor=value)}
  TextFieldRow {id:profile;first:true;last:true;label:Tr.tr("Profile file");placeholderText:"usr.bin.example";onValueEdited:value=>profile.value=value}
  RowButton {text:Tr.tr("Load policy for editing");icon:"edit_document";disabled:root.backend.busy||!profile.value;onClicked:root.backend.call("apps.apparmor-read",{profile:profile.value},value=>{if(!value.error){root.policy=value;root.policyText=value.content;}})}
  TextArea {visible:!!root.policy.sha256;Layout.fillWidth:true;Layout.preferredHeight:240*Tokens.scale;wrapMode:TextEdit.Wrap;selectByMouse:true;text:root.policyText;color:Colours.palette.m3onSurface;onTextChanged:if(activeFocus)root.policyText=text;background:Rectangle {color:Colours.palette.m3surfaceContainerHigh;radius:Tokens.rounding.medium}}
  RowButton {visible:!!root.policy.sha256;text:Tr.tr("Validate and save policy");subtext:Tr.tr("Requires administrator authorization. Saves a backup and validates syntax before replacing the file; use Enforce to load the saved policy.");icon:"save";onClicked:root.backend.call("apps.apparmor-save",{profile:root.policy.profile,sha256:root.policy.sha256,content:root.policyText},()=>root.policy=({}))}
  InfoRow {first:true;last:true;label:Tr.tr("Available policy files");value:(root.armor.profileFiles??[]).join(", ")}
  Repeater {model:[{id:"enforce",name:Tr.tr("Enforce restrictions")},{id:"complain",name:Tr.tr("Complain mode (log only)")},{id:"disable-profile",name:Tr.tr("Disable this profile")}];RowButton {required property var modelData;text:modelData.name;icon:"admin_panel_settings";disabled:root.backend.busy||!profile.value;onClicked:root.backend.call("apps.apparmor-mode",{profile:profile.value,mode:modelData.id},()=>root.backend.call("apps.apparmor-status",{},value=>root.armor=value))}}
 }
 SettingsCard {
  visible:!!root.details.package
  title:Tr.tr("Installed package");icon:"inventory_2"
  InfoRow {first:true;last:true;label:root.details.package??"";value:root.details.version??""}
  RowButton {first:true;last:true;text:Tr.tr("Remove application");subtext:Tr.tr("Removes the owning package, including its other launchers. Pacman keeps dependency checks; critical system packages are protected.");icon:"delete";disabled:root.backend.busy;onClicked:root.backend.call("apps.remove",{id:root.application.id,version:root.details.version})}
 }
}
