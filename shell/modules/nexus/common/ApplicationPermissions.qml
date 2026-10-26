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
 property var portals:({})
 function reloadPortals():void {if(!application)return;const id=application.id;backend.call("apps.portal-status",{id:details.flatpak||id.replace(/\.desktop$/,"" )},value=>{if(root.application?.id===id)root.portals=value;});}
 property string selectedProfile:""
 property var policy:({})
 property string policyText:""
 property var restrictions:({})
  property string armorNotice:""
 function loadArmorProfile(name):void {selectedProfile=name;policy=({});armorNotice="";backend.call("apps.apparmor-read",{profile:name},value=>{if(!value.error&&root.selectedProfile===name){policy=value;policyText=value.content;restrictions=value.restrictions??{};}});}
 property bool folderReadOnly:true
 property FolderDialog folderGrant:FolderDialog {onAccepted:root.backend.call("apps.flatpak-override",{id:root.details.flatpak,options:["--filesystem="+Paths.toLocalFile(selectedFolder)+(root.folderReadOnly?":ro":":rw")]},()=>root.reload())}
 property bool advanced:false
 property DesktopBackend backend:DesktopBackend{}
 Layout.fillWidth:true;spacing:Tokens.spacing.large
 function reload():void {if(!application)return;const id=application.id;const path=application.filePath;backend.call("apps.info",{id:id,path:path},value=>{if(!value.error&&root.application?.id===id&&root.application?.filePath===path)root.details=value;});}
 onApplicationChanged:{details=({});portals=({});policy=({});selectedProfile="";reload();}
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
  SettingsCard {
   title:Tr.tr("Desktop portal permissions");icon:"security";collapsible:true;expanded:false
   description:Tr.tr("These permissions apply only when an application uses the desktop portal. They do not revoke direct hardware access or stop an existing capture session. Default restores the portal's own policy; notification portals normally allow notifications by default.")
   onExpandedChanged:if(expanded)root.reloadPortals()
   RowButton {text:Tr.tr("Refresh portal permissions");icon:"refresh";disabled:root.backend.busy;onClicked:root.reloadPortals()}
   Repeater {
    model:[{id:"camera",label:"Camera portal"},{id:"background",label:"Run in the background"},{id:"notifications",label:"Notifications through the portal"}]
    ColumnLayout {
     required property var modelData;Layout.fillWidth:true
     GenericSettingRow {Layout.fillWidth:true;spec:({label:parent.modelData.label,type:"choice",choices:[{value:"default",label:"Portal default"},{value:"yes",label:"Allow"},{value:"no",label:"Deny"}],value:root.portals.permissions?.[parent.modelData.id]?.policy??"default"});onEdited:value=>root.backend.call("apps.portal-permission",{id:root.details.flatpak||root.application.id.replace(/\.desktop$/,""),kind:parent.modelData.id,policy:value},()=>root.reloadPortals())}
     FeatureError {error:root.portals.permissions?.[parent.modelData.id]?.error??""}
    }
   }
  }
  ToggleRow {first:true;last:true;text:Tr.tr("Launch at login");checked:root.details.autostart??false;onToggled:root.backend.call("apps.autostart",{id:root.application.id,path:root.application.filePath,enabled:checked},value=>{if(!value.error)root.reload();})}
  RowButton {visible:!!root.details.flatpak;first:true;last:true;text:Tr.tr("Restore default Flatpak permissions");icon:"restart_alt";disabled:root.backend.busy;onClicked:root.backend.call("apps.flatpak-reset",{id:root.details.flatpak},()=>root.reload())}
  ToggleRow {visible:!!root.details.flatpak;first:true;last:true;text:Tr.tr("Advanced Flatpak settings");checked:root.advanced;onToggled:root.advanced=checked}
  InfoRow {visible:root.advanced;first:true;last:true;label:Tr.tr("Effective permissions");value:JSON.stringify(root.details.permissions??{},null,2)}
  TextFieldRow {id:override;visible:root.advanced;first:true;last:true;label:Tr.tr("Override option");placeholderText:"--filesystem=xdg-documents:ro";onValueEdited:value=>override.value=value}
  RowButton {visible:root.advanced;text:Tr.tr("Apply override");icon:"tune";disabled:root.backend.busy||!override.value;onClicked:root.backend.call("apps.flatpak-override",{id:root.details.flatpak,options:[override.value]},()=>root.reload())}
  FeatureError {error:root.backend.error}
 }
 SettingsCard {
  objectName:"appArmorSettings"
  title:Tr.tr("AppArmor");icon:"security";collapsible:true;expanded:false
  description:Tr.tr("Choose an installed profile and adjust its mode or additional restrictions. Enabling a resource here never grants access beyond the original policy.")
  onExpandedChanged:if(expanded)root.backend.call("apps.apparmor-status",{},value=>root.armor=value)
  RowButton {text:Tr.tr("Refresh system profiles");icon:"refresh";disabled:root.backend.busy;onClicked:root.backend.call("apps.apparmor-status",{},result=>{if(!result.error)root.armor=result;})}
  InfoRow {label:Tr.tr("Kernel enforcement");value:root.armor.apparmorActive?Tr.tr("AppArmor is active"):Tr.tr("AppArmor is unavailable or not enabled in the kernel")}
  ToggleRow {text:Tr.tr("Enable AppArmor at startup");subtext:Tr.tr("System-wide setting; requires AppArmor support in the running kernel");checked:root.armor.apparmorServiceEnabled??false;enabled:!root.backend.busy;onToggled:root.backend.call("apps.apparmor-service",{enabled:checked},value=>root.armor=value)}
  GenericSettingRow {spec:({label:"Installed profile",type:"choice",choices:[{value:"",label:"Choose a profile"},...(root.armor.profileFiles??[]).map(name=>({value:name,label:name}))],value:root.selectedProfile});onEdited:value=>{if(value)root.loadArmorProfile(value);}}
  InfoRow {visible:!!root.selectedProfile;label:Tr.tr("Loaded profile modes");value:String((root.armor.profiles??[]).length)}
  SettingsCard {
   objectName:"appArmorVisualRestrictions"
   visible:!!root.policy.guiSupported;title:Tr.tr("Additional restrictions");icon:"shield"
   description:Tr.tr("Stored in the profile's standard local include. These are direct device and file restrictions; camera or audio access through portals and PipeWire is controlled separately. Saving does not change the running mode; use Enforce to load the policy.")
   Repeater {
    model:[{key:"network",label:"Block IPv4 and IPv6 networking"},{key:"camera",label:"Block direct camera device access"},{key:"audio",label:"Block direct sound device access"},{key:"home",label:"Block home folder file access"},{key:"removable",label:"Block removable and mounted folders"}]
    ToggleRow {required property var modelData;text:Tr.tr(modelData.label);checked:root.restrictions[modelData.key]??false;enabled:!root.backend.busy;onToggled:root.restrictions=Object.assign({},root.restrictions,{[modelData.key]:checked})}
   }
   RowButton {text:Tr.tr("Save restrictions");icon:"save";disabled:root.backend.busy;onClicked:root.backend.call("apps.apparmor-controls",{profile:root.policy.profile,sha256:root.policy.sha256,localSha256:root.policy.localSha256,restrictions:root.restrictions},value=>{if(!value.error){root.loadArmorProfile(root.selectedProfile);root.armorNotice=Tr.tr("Restrictions saved. Choose Enforce restrictions to load the saved policy.");}})}
  }
  InfoRow {visible:!!root.policy.sha256&&!root.policy.guiSupported;label:Tr.tr("Visual restrictions");value:Tr.tr("This profile has no standard local include. Its mode can still be changed; arbitrary policy syntax remains in the advanced editor.")}
  InfoRow {visible:!!root.armorNotice;label:Tr.tr("Policy changes");value:root.armorNotice}
  Repeater {model:[{id:"enforce",name:"Enforce restrictions"},{id:"complain",name:"Complain mode (log only)"},{id:"disable-profile",name:"Disable this profile"}];RowButton {required property var modelData;text:Tr.tr(modelData.name);icon:"admin_panel_settings";disabled:root.backend.busy||!root.selectedProfile;onClicked:root.backend.call("apps.apparmor-mode",{profile:root.selectedProfile,mode:modelData.id},()=>{root.armorNotice="";root.backend.call("apps.apparmor-status",{},value=>root.armor=value);})}}
  SettingsCard {
   visible:!!root.policy.sha256;title:Tr.tr("Advanced policy editor");icon:"code";collapsible:true;expanded:false
   description:Tr.tr("For policy syntax that cannot be represented by the visual controls. A backup and syntax validation are required before replacement.")
   TextArea {Layout.fillWidth:true;Layout.preferredHeight:240*Tokens.scale;wrapMode:TextEdit.Wrap;selectByMouse:true;text:root.policyText;color:Colours.palette.m3onSurface;onTextChanged:if(activeFocus)root.policyText=text;background:Rectangle {color:Colours.palette.m3surfaceContainerHigh;radius:Tokens.rounding.medium}}
   RowButton {text:Tr.tr("Validate and save policy");icon:"save";disabled:root.backend.busy;onClicked:root.backend.call("apps.apparmor-save",{profile:root.policy.profile,sha256:root.policy.sha256,content:root.policyText},()=>root.loadArmorProfile(root.selectedProfile))}
  }
  FeatureError {error:root.backend.error}
 }

 SettingsCard {
  visible:!!root.details.package
  title:Tr.tr("Installed package");icon:"inventory_2"
  InfoRow {first:true;last:true;label:root.details.package??"";value:root.details.version??""}
  RowButton {first:true;last:true;text:Tr.tr("Remove application");subtext:Tr.tr("Removes the owning package, including its other launchers. Pacman keeps dependency checks; critical system packages are protected.");icon:"delete";disabled:root.backend.busy;onClicked:root.backend.call("apps.remove",{id:root.application.id,version:root.details.version})}
 }
}
