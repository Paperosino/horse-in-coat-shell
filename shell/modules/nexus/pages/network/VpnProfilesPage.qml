pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import QtQuick.Dialogs
import Hyprstack.Config
import Hyprstack.I18n
import Hyprstack.Services
import qs.modules.nexus.common
PageBase {
    id:root
    title:Tr.tr("VPN")
    property string selectedService:"wireguard"
    property string removingPath
    property string exportPath
    property bool openEditor:false
    Component.onCompleted:NetworkManagerVpn.refresh()
    readonly property Timer refreshTimer: Timer { interval:4000; repeat:true; running:root.visible; onTriggered:if(!NetworkManagerVpn.busy)NetworkManagerVpn.refresh() }
    readonly property Connections vpnConnections: Connections {
        target:NetworkManagerVpn
        function onDraftChanged():void {
            if(root.openEditor && NetworkManagerVpn.draft.type) {root.openEditor=false;root.nState.openSubPage(1)}
        }
    }
    readonly property FileDialog importDialog: FileDialog { id:importer; title:Tr.tr("Import VPN configuration"); onAccepted:{root.openEditor=true;NetworkManagerVpn.importFile(root.selectedService,selectedFile)} }
    readonly property FileDialog exportDialog: FileDialog { id:exporter; title:Tr.tr("Export VPN configuration"); fileMode:FileDialog.SaveFile;nameFilters:["NetworkManager (*.nmconnection)","VPN configuration (*.conf *.ovpn)"];defaultSuffix:"nmconnection"; onAccepted:NetworkManagerVpn.exportFile(root.exportPath,selectedFile) }
    ColumnLayout {
        width:root.cappedWidth;anchors.horizontalCenter:parent.horizontalCenter;spacing:Tokens.spacing.extraSmall/2
        SettingsGuide { icon:"vpn_key";title:Tr.tr("NetworkManager VPN connections");description:Tr.tr("Manage saved VPN profiles, certificates, DNS and routes. Imported and existing profiles keep their plugin-specific settings.");badges:["OpenVPN","WireGuard","L2TP/IPsec","PPTP"] }
        FeatureError { error:NetworkManagerVpn.error }
        SectionHeader { first:true;text:Tr.tr("Saved VPN connections") }
        Repeater {
            model:NetworkManagerVpn.profiles
            ColumnLayout {
                id:profile
                required property var modelData
                Layout.fillWidth:true;spacing:Tokens.spacing.extraSmall/2
                InfoRow { first:true;label:profile.modelData.name;value:profile.modelData.active ? (profile.modelData.state===2?Tr.tr("Connected"):Tr.tr("Connecting")):Tr.tr("Disconnected") }
                RowButton { text:profile.modelData.active?Tr.tr("Disconnect"):Tr.tr("Connect");icon:profile.modelData.active?"vpn_key_off":"vpn_key";disabled:NetworkManagerVpn.busy;onClicked:profile.modelData.active?NetworkManagerVpn.deactivate(profile.modelData.activePath):NetworkManagerVpn.activate(profile.modelData.path) }
                RowButton { text:Tr.tr("Edit connection");icon:"edit";disabled:NetworkManagerVpn.busy;onClicked:{root.openEditor=true;NetworkManagerVpn.edit(profile.modelData.path)} }
                RowButton { visible:NetworkManagerVpn.plugins.some(p=>p.service===profile.modelData.type&&p.canExport);text:Tr.tr("Export configuration");subtext:Tr.tr("The export contains private credentials. Keep it secure.");icon:"file_save";disabled:NetworkManagerVpn.busy;onClicked:{root.exportPath=profile.modelData.path;exporter.open()} }
                RowButton {text:Tr.tr("Export NetworkManager profile");subtext:Tr.tr("The export contains private credentials. Keep it secure.");icon:"file_save";disabled:NetworkManagerVpn.busy;onClicked:{root.exportPath=profile.modelData.path;exporter.open()}}
                RowButton { last:true;text:Tr.tr("Delete connection");icon:"delete";disabled:NetworkManagerVpn.busy;onClicked:root.removingPath=profile.modelData.path }
                RowButton { visible:root.removingPath===profile.modelData.path;text:Tr.tr("Confirm deletion");icon:"delete_forever";disabled:NetworkManagerVpn.busy;onClicked:{NetworkManagerVpn.remove(profile.modelData.path);root.removingPath=""} }
                RowButton { visible:root.removingPath===profile.modelData.path;text:Tr.tr("Cancel");icon:"close";onClicked:root.removingPath="" }
            }
        }
        InfoRow { visible:!NetworkManagerVpn.profiles.length;first:true;last:true;label:Tr.tr("No VPN connections");value:Tr.tr("Create a connection or import a configuration file") }
        SectionHeader { text:Tr.tr("Add VPN connection") }
        Repeater {
            model:NetworkManagerVpn.plugins
            ColumnLayout {
                id:protocol
                required property var modelData
                Layout.fillWidth:true;spacing:Tokens.spacing.extraSmall/2
                RowButton { first:true;last:!protocol.modelData.canImport;text:protocol.modelData.name;subtext:protocol.modelData.installed?Tr.tr("Create a profile"):Tr.tr("Plugin not installed")+" · "+protocol.modelData.package;icon:"add";disabled:NetworkManagerVpn.busy||!protocol.modelData.installed;onClicked:{root.openEditor=true;NetworkManagerVpn.create(protocol.modelData.service)} }
                RowButton { visible:!!protocol.modelData.canImport;last:true;text:Tr.tr("Import configuration")+" · "+protocol.modelData.name;icon:"file_open";disabled:NetworkManagerVpn.busy||!protocol.modelData.installed;onClicked:{root.selectedService=protocol.modelData.service;importer.open()} }
            }
        }
        NavRow {first:true;last:true;text:Tr.tr("NetworkManager VPN plugins");icon:"extension";subtext:Tr.tr("Installed protocols, import support and plugin packages");onClicked:root.nState.openSubPage(2)}
    }
}
