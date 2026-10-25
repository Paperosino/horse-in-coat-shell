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
 title:Tr.tr("Device firmware");pageIcon:"system_update"
 property var state:({})
 property string confirming:""
 property var history:[]
 property DesktopBackend backend:DesktopBackend {}
 function refresh():void {backend.call("firmware.status",{},value=>{if(!value.error)root.state=value;});}
 function releases(id):var {return (state.updates?.Devices??[]).find(d=>d.DeviceId===id)?.Releases??[];}
 Component.onCompleted:refresh()
 ColumnLayout {
  width:root.cappedWidth;anchors.horizontalCenter:parent.horizontalCenter;spacing:Tokens.spacing.large
  SettingsCard {
   title:Tr.tr("Firmware from your device vendor");icon:"verified_user"
   description:Tr.tr("fwupd verifies firmware and enforces device and power requirements. Connect AC power, keep the device connected, and save your work before updating.")
   RowButton {text:Tr.tr("Check installed devices");icon:"refresh";disabled:root.backend.busy;onClicked:root.refresh()}
   RowButton {text:Tr.tr("Refresh firmware metadata");icon:"sync";subtext:Tr.tr("Downloads the latest metadata from configured fwupd remotes.");disabled:root.state.available===false||root.backend.busy;onClicked:root.backend.call("firmware.refresh",{},value=>{if(!value.error)root.refresh();})}
   InfoRow {visible:root.state.available===false;label:"fwupd";value:Tr.tr("Install fwupd to manage supported device firmware.")}
  }
  Repeater {model:root.state.Devices??[]
   SettingsCard {id:device;required property var modelData;title:modelData.Name??modelData.DeviceId;icon:"memory";badge:root.releases(modelData.DeviceId).length?Tr.tr("Update available"):""
    InfoRow {label:Tr.tr("Installed version");value:device.modelData.Version??""}
    InfoRow {visible:(device.modelData.Flags??[]).some(flag=>flag==="needs-reboot"||flag==="needs-shutdown");label:Tr.tr("Complete the update");value:Tr.tr("Save your work and restart or shut down as requested by fwupd.")}
    InfoRow {visible:!!device.modelData.UpdateError;label:Tr.tr("Requirements");value:device.modelData.UpdateError??""}
    Repeater {model:root.releases(device.modelData.DeviceId)
     InfoRow {required property var modelData;label:Tr.tr("Available version");value:modelData.Version??""}
    }
    RowButton {visible:root.releases(device.modelData.DeviceId).length>0;text:root.confirming===device.modelData.DeviceId?Tr.tr("Confirm and open firmware updater"):Tr.tr("Update this device");icon:"system_update";subtext:Tr.tr("The upstream updater opens in a terminal for power checks and any unplug/replug instructions. It asks before rebooting.");disabled:root.backend.busy;onClicked:{if(root.confirming!==device.modelData.DeviceId){root.confirming=device.modelData.DeviceId;return;}root.backend.call("firmware.update",{id:device.modelData.DeviceId,confirmed:true});root.confirming="";}}
   }
  }
  SettingsCard {
   title:Tr.tr("Firmware update history");icon:"history";collapsible:true;expanded:false
   RowButton {text:Tr.tr("Read update history");icon:"refresh";disabled:root.backend.busy;onClicked:root.backend.call("firmware.history",{},value=>{if(!value.error)root.history=value.Devices??[];})}
   Repeater {model:root.history
    InfoRow {required property var modelData;label:modelData.Name??modelData.DeviceId;value:String(modelData.Version??"")+" · "+String(modelData.UpdateState??"")+(modelData.UpdateError?" · "+modelData.UpdateError:"")}
   }
  }
  FeatureError {error:root.state.updateError??""}
  FeatureError {error:root.backend.error}
 }
}
