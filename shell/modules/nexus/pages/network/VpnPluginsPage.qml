pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import Hyprstack.Config
import Hyprstack.I18n
import Hyprstack.Services
import qs.modules.nexus.common
PageBase {
    id:root
    title:Tr.tr("NetworkManager VPN plugins")
    Component.onCompleted:NetworkManagerVpn.refresh()
    ColumnLayout {
        width:root.cappedWidth;anchors.horizontalCenter:parent.horizontalCenter;spacing:Tokens.spacing.extraSmall/2
        FeatureError {error:NetworkManagerVpn.error}
        InfoRow {first:true;last:true;label:Tr.tr("Plugin support");value:Tr.tr("Installed NetworkManager plugins are discovered automatically. WireGuard is built into NetworkManager.")}
        Repeater {
            model:NetworkManagerVpn.plugins
            ColumnLayout {
                id:plugin
                required property var modelData
                Layout.fillWidth:true
                InfoRow {
                first:true;last:true
                label:plugin.modelData.name
                value:(plugin.modelData.installed?Tr.tr("Installed"):Tr.tr("Not installed"))+(plugin.modelData.package?" · "+plugin.modelData.package:"")+(plugin.modelData.canImport?" · "+Tr.tr("Import supported"):"")+(plugin.modelData.canExport?" · "+Tr.tr("Export supported"):"")
                }
                RowButton {visible:!plugin.modelData.installed&&!!plugin.modelData.package;text:Tr.tr("Install plugin");icon:"download";disabled:NetworkManagerVpn.busy;onClicked:NetworkManagerVpn.installPlugin(plugin.modelData.id)}
            }
        }
        RowButton {first:true;last:true;text:Tr.tr("Refresh");icon:"refresh";disabled:NetworkManagerVpn.busy;onClicked:NetworkManagerVpn.refresh()}
    }
}
