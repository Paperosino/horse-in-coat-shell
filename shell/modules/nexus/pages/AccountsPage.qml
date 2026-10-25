pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import Hyprstack.Config
import Hyprstack.I18n
import qs.components
import qs.services
import qs.modules.nexus.common
PageBase {
 id:root
 title:Tr.tr("Users & sign-in");pageIcon:"manage_accounts"
 property var state:({})
 property var selected:null
 property string newName:""
 property string newRealName:""
 property bool newAdministrator:false
 property string confirmSession:""
 property string confirmFinger:""
 property DesktopBackend backend:DesktopBackend {}
 function refresh():void {backend.call("accounts.status",{},value=>{if(!value.error){root.state=value;if(root.selected)root.selected=(value.users??[]).find(u=>u.path===root.selected.path)??null;}});}
 function change(operation,args):void {backend.call(operation,args,value=>{if(!value.error)root.refresh();});}
 Component.onCompleted:refresh()
 ColumnLayout {
  width:root.cappedWidth;anchors.horizontalCenter:parent.horizontalCenter;spacing:Tokens.spacing.large
  SettingsCard {
   title:Tr.tr("People on this computer");icon:"group"
   description:Tr.tr("Account changes use the system's AccountsService and polkit authorization.")
   RowButton {text:Tr.tr("Refresh");icon:"refresh";disabled:root.backend.busy;onClicked:root.refresh()}
   Repeater {model:root.state.users??[]
    RowButton {required property var modelData;text:modelData.realName||modelData.name;subtext:modelData.name+" · "+(modelData.administrator?Tr.tr("Administrator"):Tr.tr("Standard user"))+(modelData.current?" · "+Tr.tr("You"):"");icon:root.selected?.path===modelData.path?"check_circle":"person";onClicked:root.selected=modelData}
   }
  }
  SettingsCard {
   visible:!!root.selected;title:root.selected?.realName||root.selected?.name||"";icon:"manage_accounts"
   TextFieldRow {label:Tr.tr("Display name");maximumLength:128;value:root.selected?.realName??"";onEditingFinished:value=>{if(value.trim()&&value!==root.selected?.realName)root.change("accounts.rename",{path:root.selected.path,realName:value});}}
   ToggleRow {text:Tr.tr("Administrator");subtext:Tr.tr("The last available administrator cannot be demoted.");checked:root.selected?.administrator??false;onToggled:root.change("accounts.role",{path:root.selected.path,administrator:checked})}
   RowButton {text:root.selected?.current?Tr.tr("Change my password"):Tr.tr("Set this user's password");icon:"password";subtext:Tr.tr("Opens the system password tool. Administrator resets do not unlock an existing encrypted keyring.");disabled:root.backend.busy;onClicked:root.backend.call("accounts.password",{name:root.selected.name,current:root.selected.current})}
  }
  SettingsCard {
   title:Tr.tr("Add a user");icon:"person_add";collapsible:true;expanded:false
   description:Tr.tr("Create the account, then select it above and set its initial password. Until then it cannot sign in.")
   TextFieldRow {label:Tr.tr("User name");value:root.newName;maximumLength:32;placeholderText:"alex";onValueEdited:value=>root.newName=value}
   TextFieldRow {label:Tr.tr("Display name");value:root.newRealName;maximumLength:128;onValueEdited:value=>root.newRealName=value}
   ToggleRow {text:Tr.tr("Administrator");checked:root.newAdministrator;onToggled:root.newAdministrator=checked}
   RowButton {text:Tr.tr("Create user");icon:"person_add";disabled:root.backend.busy||!/^[a-z_][a-z0-9_-]{0,31}$/.test(root.newName);onClicked:root.change("accounts.create",{name:root.newName,realName:root.newRealName,administrator:root.newAdministrator})}
  }
  SettingsCard {
   title:Tr.tr("Active sessions");icon:"devices";collapsible:true;expanded:false
   description:Tr.tr("Ending another session closes its applications. Save its work first.")
   Repeater {model:root.state.sessions??[]
    SettingsCard {id:session;required property var modelData;title:modelData.user+" · "+modelData.id;icon:"desktop_windows"
     RowButton {text:Tr.tr("Switch to this session");icon:"switch_account";disabled:session.modelData.current||root.backend.busy;onClicked:root.change("accounts.activate",{id:session.modelData.id})}
     RowButton {text:root.confirmSession===session.modelData.id?Tr.tr("Confirm ending this session"):Tr.tr("End session");icon:"logout";disabled:session.modelData.current||root.backend.busy;onClicked:{if(root.confirmSession!==session.modelData.id){root.confirmSession=session.modelData.id;return;}root.change("accounts.terminate",{id:session.modelData.id,confirmed:true});root.confirmSession="";}}
    }
   }
  }
  SettingsCard {
   title:Tr.tr("Fingerprint");icon:"fingerprint";description:root.state.fingerprintReader||Tr.tr("A compatible reader and fprintd are required.")
   Repeater {model:root.state.fingers??[]
    SettingsCard {id:enrolled;required property string modelData;title:Tr.tr(modelData);icon:"fingerprint"
     RowButton {text:Tr.tr("Verify fingerprint");icon:"verified_user";disabled:root.backend.busy;onClicked:root.backend.call("accounts.fingerprint-verify",{finger:enrolled.modelData})}
     RowButton {text:root.confirmFinger===enrolled.modelData?Tr.tr("Confirm removing fingerprint"):Tr.tr("Remove fingerprint");icon:"delete";disabled:root.backend.busy;onClicked:{if(root.confirmFinger!==enrolled.modelData){root.confirmFinger=enrolled.modelData;return;}root.change("accounts.fingerprint-delete",{finger:enrolled.modelData,confirmed:true});root.confirmFinger="";}}
    }
   }
   InfoRow {visible:!(root.state.fingers??[]).length;label:Tr.tr("Enrolled fingers");value:Tr.tr("None")}
   GenericSettingRow {id:finger;property string choice:"right-index-finger";spec:({label:"Finger",type:"choice",choices:["right-index-finger","right-thumb","left-index-finger","left-thumb","right-middle-finger","right-ring-finger","right-little-finger","left-middle-finger","left-ring-finger","left-little-finger"],value:choice});onEdited:value=>choice=value}
   RowButton {text:Tr.tr("Enrol fingerprint");subtext:Tr.tr("Follow the reader instructions in the system enrolment tool, then refresh. This does not change your PAM login policy.");icon:"fingerprint";disabled:!root.state.fingerprintReader||root.backend.busy;onClicked:root.backend.call("accounts.fingerprint-enroll",{finger:finger.choice})}
  }
  FeatureError {error:root.backend.error}
 }
}
