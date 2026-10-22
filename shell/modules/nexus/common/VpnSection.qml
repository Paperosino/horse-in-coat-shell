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
    property var vpnBackend:NetworkManagerVpn
    property string removingPath
    property int editorPage:7
    property int pluginsPage:8
    property bool choosingType:false
    property bool openingEditor:false
    property string selectedService:"org.freedesktop.NetworkManager.openvpn"
    readonly property var availableProtocols:root.vpnBackend.plugins.filter(p=>p.installed)
    onAvailableProtocolsChanged:if(availableProtocols.length&&!availableProtocols.some(p=>p.service===selectedService))selectedService=availableProtocols[0].service
    Layout.fillWidth:true
    spacing:Tokens.spacing.extraSmall/2
    objectName:"networkVpnSection"
    function edit(path):void {openingEditor=true;root.vpnBackend.edit(path)}
    function create():void {openingEditor=true;root.vpnBackend.create(selectedService)}
    Component.onCompleted:root.vpnBackend.refresh()
    Timer {interval:5000;repeat:true;running:root.visible;onTriggered:if(!root.vpnBackend.busy)root.vpnBackend.refresh()}
    Connections {
        target:root.vpnBackend
        function onChanged():void {if(!root.vpnBackend.busy&&root.vpnBackend.error)root.openingEditor=false}
        function onDraftChanged():void {if(root.openingEditor&&root.vpnBackend.draft.type){root.openingEditor=false;root.nState.openSubPage(root.editorPage)}}
    }
    FileDialog {id:importer;title:Tr.tr("Import VPN configuration");onAccepted:{root.openingEditor=true;root.vpnBackend.importFile(root.selectedService,selectedFile)}}
    SectionHeader {text:Tr.tr("VPN")}
    FeatureError {error:root.vpnBackend.error}
    Repeater {
        model:root.vpnBackend.profiles
        ConnectedRect {
            id:profile
            required property var modelData
            required property int index
            Layout.fillWidth:true
            first:index===0;last:index===root.vpnBackend.profiles.length-1
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
                IconButton {Accessible.name:Tr.tr("Edit connection");icon:"edit";type:IconButton.Text;disabled:root.vpnBackend.busy;onClicked:root.edit(profile.modelData.path)}
                IconButton {objectName:"vpnDeleteButton";Accessible.name:Tr.tr("Delete connection");icon:"delete";type:IconButton.Text;disabled:root.vpnBackend.busy;onClicked:root.removingPath=profile.modelData.path}
                IconButton {Accessible.name:profile.modelData.active?Tr.tr("Disconnect"):Tr.tr("Connect");icon:profile.modelData.active?"link_off":"link";disabled:root.vpnBackend.busy;onClicked:profile.modelData.active?root.vpnBackend.deactivate(profile.modelData.activePath):root.vpnBackend.activate(profile.modelData.path)}
            }
        }
    }
    RowButton {objectName:"vpnConfirmDelete";visible:!!root.removingPath;first:true;text:Tr.tr("Confirm deletion");subtext:root.vpnBackend.profiles.find(p=>p.path===root.removingPath)?.name??"";icon:"delete_forever";disabled:root.vpnBackend.busy;onClicked:{root.vpnBackend.remove(root.removingPath);root.removingPath=""}}
    RowButton {visible:!!root.removingPath;last:true;text:Tr.tr("Cancel");icon:"close";onClicked:root.removingPath=""}
    InfoRow {visible:!root.vpnBackend.profiles.length;first:true;last:true;label:Tr.tr("No VPN connections");value:Tr.tr("Create a connection or import a configuration file")}
    RowButton {first:true;last:!root.choosingType;text:Tr.tr("Add VPN connection");icon:"add";onClicked:root.choosingType=!root.choosingType}
    ColumnLayout {
        visible:root.choosingType;Layout.fillWidth:true;spacing:Tokens.spacing.extraSmall/2
        GenericSettingRow {spec:({label:"Protocol",type:"choice",choices:root.availableProtocols.map(p=>({label:p.name,value:p.service}))});value:root.selectedService;onEdited:v=>root.selectedService=v}
        RowButton {text:Tr.tr("Create a profile");icon:"add";disabled:root.vpnBackend.busy||!root.availableProtocols.some(p=>p.service===root.selectedService);onClicked:root.create()}
        RowButton {last:true;text:Tr.tr("Import configuration");icon:"file_open";disabled:root.vpnBackend.busy;onClicked:importer.open()}
    }
    RowButton {first:true;last:true;text:Tr.tr("NetworkManager VPN plugins");icon:"extension";onClicked:root.nState.openSubPage(root.pluginsPage)}
}
