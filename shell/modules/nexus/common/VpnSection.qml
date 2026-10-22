pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import QtQuick.Dialogs
import Hyprstack.Config
import Hyprstack.I18n
import Hyprstack.Services
import qs.components
import qs.components.controls
import qs.modules.nexus

ColumnLayout {
    id: root
    required property NexusState nState
    property int editorPage:7
    property int pluginsPage:8
    property bool choosingType:false
    property bool openingEditor:false
    property string selectedService:"org.freedesktop.NetworkManager.openvpn"
    readonly property var availableProtocols:NetworkManagerVpn.plugins.filter(p=>p.installed)
    onAvailableProtocolsChanged:if(availableProtocols.length&&!availableProtocols.some(p=>p.service===selectedService))selectedService=availableProtocols[0].service
    Layout.fillWidth:true
    spacing:Tokens.spacing.extraSmall/2
    objectName:"networkVpnSection"
    function edit(path):void {openingEditor=true;NetworkManagerVpn.edit(path)}
    function create():void {openingEditor=true;NetworkManagerVpn.create(selectedService)}
    Component.onCompleted:NetworkManagerVpn.refresh()
    Timer {interval:5000;repeat:true;running:root.visible;onTriggered:if(!NetworkManagerVpn.busy)NetworkManagerVpn.refresh()}
    Connections {
        target:NetworkManagerVpn
        function onChanged():void {if(!NetworkManagerVpn.busy&&NetworkManagerVpn.error)root.openingEditor=false}
        function onDraftChanged():void {if(root.openingEditor&&NetworkManagerVpn.draft.type){root.openingEditor=false;root.nState.openSubPage(root.editorPage)}}
    }
    FileDialog {id:importer;title:Tr.tr("Import VPN configuration");onAccepted:{root.openingEditor=true;NetworkManagerVpn.importFile(root.selectedService,selectedFile)}}
    SectionHeader {text:Tr.tr("VPN")}
    FeatureError {error:NetworkManagerVpn.error}
    Repeater {
        model:NetworkManagerVpn.profiles
        ConnectedRect {
            id:profile
            required property var modelData
            required property int index
            Layout.fillWidth:true
            first:index===0;last:index===NetworkManagerVpn.profiles.length-1
            implicitHeight:profileRow.implicitHeight+Tokens.padding.medium*2
            RowLayout {
                id:profileRow
                anchors.left:parent.left;anchors.right:parent.right;anchors.verticalCenter:parent.verticalCenter;anchors.margins:Tokens.padding.largeIncreased
                spacing:Tokens.spacing.small
                MaterialIcon {text:"vpn_key"}
                ColumnLayout {
                    Layout.fillWidth:true;Layout.minimumWidth:0;spacing:0
                    StyledText {Layout.fillWidth:true;text:profile.modelData.name;elide:Text.ElideRight}
                    StyledText {Layout.fillWidth:true;text:profile.modelData.active?(profile.modelData.state===2?Tr.tr("Connected"):Tr.tr("Connecting")):Tr.tr("Disconnected");font:Tokens.font.body.small;elide:Text.ElideRight}
                }
                IconButton {Accessible.name:Tr.tr("Edit connection");icon:"edit";type:IconButton.Text;disabled:NetworkManagerVpn.busy;onClicked:root.edit(profile.modelData.path)}
                IconButton {Accessible.name:profile.modelData.active?Tr.tr("Disconnect"):Tr.tr("Connect");icon:profile.modelData.active?"link_off":"link";disabled:NetworkManagerVpn.busy;onClicked:profile.modelData.active?NetworkManagerVpn.deactivate(profile.modelData.activePath):NetworkManagerVpn.activate(profile.modelData.path)}
            }
        }
    }
    InfoRow {visible:!NetworkManagerVpn.profiles.length;first:true;last:true;label:Tr.tr("No VPN connections");value:Tr.tr("Create a connection or import a configuration file")}
    RowButton {first:true;last:!root.choosingType;text:Tr.tr("Add VPN connection");icon:"add";onClicked:root.choosingType=!root.choosingType}
    ColumnLayout {
        visible:root.choosingType;Layout.fillWidth:true;spacing:Tokens.spacing.extraSmall/2
        GenericSettingRow {spec:({label:"Protocol",type:"choice",choices:root.availableProtocols.map(p=>({label:p.name,value:p.service}))});value:root.selectedService;onEdited:v=>root.selectedService=v}
        RowButton {text:Tr.tr("Create a profile");icon:"add";disabled:NetworkManagerVpn.busy||!root.availableProtocols.some(p=>p.service===root.selectedService);onClicked:root.create()}
        RowButton {last:true;text:Tr.tr("Import configuration");icon:"file_open";disabled:NetworkManagerVpn.busy;onClicked:importer.open()}
    }
    RowButton {first:true;last:true;text:Tr.tr("NetworkManager VPN plugins");icon:"extension";onClicked:root.nState.openSubPage(root.pluginsPage)}
}
