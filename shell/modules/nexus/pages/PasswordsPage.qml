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
 title:Tr.tr("Passwords & keys")
 pageIcon:"key"
 property bool authorized:false
 property var collections:[]
 property var pam:[]
 property DesktopBackend backend:DesktopBackend{}
 function reload():void {if(authorized)backend.call("keyring.status",{},value=>{if(!value.error){root.collections=value.collections??[];root.pam=value.pam??[];}});}
 ColumnLayout {
  width:root.cappedWidth;anchors.horizontalCenter:parent.horizontalCenter;spacing:Tokens.spacing.large
  SettingsCard {
   title:Tr.tr("Your existing password vault");icon:"encrypted"
   description:Tr.tr("Uses the active Secret Service. hics does not create its own cryptography or send passwords to the system broker.")
   RowButton {first:true;last:true;visible:!root.authorized;text:Tr.tr("Authenticate to manage passwords");icon:"lock";disabled:root.backend.busy;onClicked:root.backend.call("keyring.authorize",{},result=>{if(!result.error){root.authorized=true;root.reload();}})}
   RowButton {first:true;last:true;visible:root.authorized;text:Tr.tr("Open the password manager");subtext:Tr.tr("Create entries, change vault passwords and manage application secrets in Seahorse");icon:"key";disabled:root.backend.busy;onClicked:root.backend.call("keyring.manager",{})}
   FeatureError {error:root.backend.error}
  }
  Repeater {
   model:root.authorized?root.collections:[]
   SettingsCard {
    required property var modelData
    title:modelData.label;icon:modelData.locked?"lock":"lock_open"
    badge:modelData.locked?Tr.tr("Locked"):Tr.tr("Unlocked")
    RowButton {first:true;last:true;text:modelData.locked?Tr.tr("Unlock vault"):Tr.tr("Lock vault");icon:modelData.locked?"lock_open":"lock";disabled:root.backend.busy;onClicked:root.backend.call(modelData.locked?"keyring.unlock":"keyring.lock",{path:modelData.path},()=>root.reload())}
   }
  }
  SettingsCard {
   title:Tr.tr("Login and recovery");icon:"passkey"
   Repeater {model:root.pam;InfoRow {required property var modelData;label:modelData.loginManager;value:modelData.passwordless?Tr.tr("Passwordless login requires the vault password"):modelData.unlockOnLogin?(modelData.passwordSync?Tr.tr("Login unlock and password synchronization configured"):Tr.tr("Login unlock configured")):Tr.tr("No automatic login unlock hook detected")}}
   InfoRow {first:true;last:true;label:Tr.tr("Automatic unlock");value:Tr.tr("The login manager can unlock the login vault using your login password through PAM. Passwordless login may still require the vault password.")}
   InfoRow {first:true;last:true;label:Tr.tr("After changing your password");value:Tr.tr("If the old vault password no longer matches your login password, change the vault password in the password manager using its old password. An administrator resetting your account password cannot decrypt the old vault.")}
   InfoRow {first:true;last:true;label:Tr.tr("Authorization boundary");value:Tr.tr("Polkit confirms access to this management screen. It does not replace vault encryption or restrict every Secret Service client.")}
  }
 }
}
