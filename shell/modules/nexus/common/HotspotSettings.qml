pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import Hyprstack.Config
import Hyprstack.I18n
import Hyprstack.Services
import qs.components
import qs.components.controls
import qs.modules.nexus.common
ColumnLayout {
    id: root
    property string adapter: DesktopIntegration.wifiDevices[0]?.path ?? ""
    spacing: Tokens.spacing.extraSmall / 2
    Layout.fillWidth: true
    SectionHeader { text: Tr.tr("Wi-Fi hotspot") }
    InfoRow { first: true; label: Tr.tr("Internet sharing"); value: Tr.tr("Starting a hotspot may disconnect Wi-Fi on this adapter") }
    InfoRow { visible: !DesktopIntegration.wifiDevices.length; label: Tr.tr("Wi-Fi"); value: Tr.tr("No Wi-Fi adapters are available") }
    Repeater {
        model: DesktopIntegration.wifiDevices
        RowButton {
            required property var modelData
            text: modelData.name
            icon: root.adapter === modelData.path ? "radio_button_checked" : "radio_button_unchecked"
            subtext: modelData.supportsAp ? "" : Tr.tr("This adapter does not support hotspot mode")
            disabled: !modelData.supportsAp
            onClicked: root.adapter = modelData.path
        }
    }
    TextFieldRow { id: ssid; label: Tr.tr("Network name"); value: "Horse hotspot"; maximumLength: 32 }
    TextFieldRow { id: password; label: Tr.tr("Password"); subtext: Tr.tr("8–63 ASCII characters"); field.echoMode: TextInput.Password; maximumLength: 63 }
    RowButton {
        text: Tr.tr("Start hotspot"); icon: "wifi_tethering"; last: true
        disabled: DesktopIntegration.busy || !DesktopIntegration.wifiDevices.some(d => d.path === root.adapter && d.supportsAp) || !ssid.field.text || password.field.text.length < 8
        onClicked: { DesktopIntegration.startHotspot(root.adapter, ssid.field.text, password.field.text); password.clear(); }
    }
    Repeater {
        model: DesktopIntegration.wifiDevices.filter(d => d.hotspot)
        RowButton {
            required property var modelData
            first: true; last: true
            text: Tr.tr("Stop hotspot") + " · " + modelData.name
            icon: "wifi_tethering_off"; disabled: DesktopIntegration.busy
            onClicked: DesktopIntegration.stopHotspot(modelData.active)
        }
    }
    FeatureError { error: DesktopIntegration.error }
}
