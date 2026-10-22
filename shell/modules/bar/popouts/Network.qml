pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import QtQuick.Controls
import Hyprstack.Config
import Hyprstack.I18n
import Hyprstack.Services
import qs.components
import qs.components.controls
import qs.services
import qs.utils
import qs.modules.nexus
import qs.modules.nexus.common

ColumnLayout {
    id:root
    required property PopoutState popouts
    property var vpnBackend:NetworkManagerVpn
    // Kept for the parent popout and password-dialog hand-off.
    property string view:"wireless"
    property string connectingToSsid:""
    property var passwordNetwork:null
    property bool showPasswordDialog:false
    readonly property int maximumVisibleRows:10
    readonly property real rowHeight:48*Tokens.scale
    readonly property real maximumListHeight:Math.max(rowHeight,Math.min(maximumVisibleRows*rowHeight,(popouts?.screen?.height??1080)*0.75-150*Tokens.scale))
    readonly property alias connectionList:connections
    property var connectionRows: {
        const rows=[];
        for(const profile of vpnBackend.profiles)rows.push({kind:"vpn",name:profile.name,active:profile.active,pending:profile.active&&profile.state!==2,data:profile});
        for(const device of Nmcli.ethernetDevices)rows.push({kind:"ethernet",name:device.connection||device.iface,active:device.connected,pending:false,data:device});
        if(Nmcli.wifiEnabled)for(const ap of Nmcli.networks)rows.push({kind:"wifi",name:ap.ssid,active:ap.active,pending:Nmcli.connectingSsid()===ap.ssid||root.connectingToSsid===ap.ssid,data:ap});
        return rows.sort((a,b)=>Number(b.active)-Number(a.active)||Number(b.pending)-Number(a.pending)||(a.kind===b.kind?(a.kind==="wifi"?b.data.strength-a.data.strength:a.name.localeCompare(b.name)):({vpn:0,ethernet:1,wifi:2}[a.kind]-{vpn:0,ethernet:1,wifi:2}[b.kind])));
    }
    spacing:Tokens.spacing.small
    width:Tokens.sizes.bar.networkWidth
    function activateRow(row):void {
        if(row.kind==="vpn"){
            if(vpnBackend.busy)return;
            if(row.active)vpnBackend.deactivate(row.data.activePath);else vpnBackend.activate(row.data.path);
        }else if(row.kind==="ethernet"){
            if(row.active&&row.data.connection)Nmcli.disconnectEthernet(row.data.connection,()=>{});
            else Nmcli.connectEthernet(row.data.connection||"",row.data.iface||"",()=>{});
        }else{
            if(row.pending)return;
            if(row.active){Nmcli.disconnectFromNetwork();return;}
            connectingToSsid=row.data.ssid;
            NetworkConnection.handleConnect(row.data,null,network=>{
                root.connectingToSsid="";root.passwordNetwork=network;root.showPasswordDialog=true;root.popouts.currentName="wirelesspassword";
            });
        }
    }
    function openSettings():void {popouts.hasCurrent=false;WindowFactory.openPage("network")}
    Component.onCompleted:if(!vpnBackend.busy)vpnBackend.refresh()
    Timer {interval:4000;running:root.visible;repeat:true;onTriggered:if(!root.vpnBackend.busy)root.vpnBackend.refresh()}
    RowLayout {
        Layout.fillWidth:true
        StyledText {Layout.fillWidth:true;text:Tr.tr("Network");font:Tokens.font.body.builders.medium.weight(Font.Medium).build()}
        IconButton {objectName:"networkSettingsButton";Accessible.name:Tr.tr("Network settings");icon:"settings";type:IconButton.Text;onClicked:root.openSettings()}
    }
    RowLayout {
        Layout.fillWidth:true
        MaterialIcon {text:"wifi"}
        StyledText {Layout.fillWidth:true;text:Tr.tr("Wi-Fi")}
        StyledSwitch {checked:Nmcli.wifiEnabled;onToggled:Nmcli.enableWifi(checked)}
        IconButton {Accessible.name:Tr.tr("Rescan networks");icon:"refresh";type:IconButton.Text;disabled:Nmcli.scanning||!Nmcli.wifiEnabled;onClicked:Nmcli.rescanWifi()}
    }
    ListView {
        id:connections
        objectName:"networkQuickConnections"
        property real preferredY:0
        Layout.fillWidth:true
        Layout.preferredHeight:Math.min(contentHeight,root.maximumListHeight)
        model:root.connectionRows
        implicitWidth:root.width
        clip:true
        boundsBehavior:Flickable.StopAtBounds
        reuseItems:true
        onMovementEnded:preferredY=contentY
        onContentYChanged:if(moving||verticalScrollBar.pressed)preferredY=contentY
        onModelChanged:Qt.callLater(()=>{contentY=Math.max(0,Math.min(preferredY,contentHeight-height))})
        ScrollBar.vertical:ScrollBar {id:verticalScrollBar;policy:ScrollBar.AsNeeded}
        delegate:Item {
            id:row
            required property var modelData
            width:ListView.view.width;height:root.rowHeight
            StateLayer {
                anchors.fill:parent
                keyboardFocusable:true
                disabled:row.modelData.kind==="vpn"?root.vpnBackend.busy:row.modelData.pending
                onClicked:root.activateRow(row.modelData)
            }
            RowLayout {
                anchors.fill:parent;anchors.leftMargin:Tokens.padding.small;anchors.rightMargin:Tokens.padding.medium
                spacing:Tokens.spacing.small
                MaterialIcon {text:row.modelData.kind==="vpn"?"vpn_key":row.modelData.kind==="ethernet"?"cable":Icons.getNetworkIcon(row.modelData.data.strength);color:row.modelData.active?Colours.palette.m3primary:Colours.palette.m3onSurfaceVariant}
                ColumnLayout {
                    Layout.fillWidth:true;Layout.minimumWidth:0;spacing:0
                    StyledText {Layout.fillWidth:true;text:row.modelData.name;elide:Text.ElideRight;maximumLineCount:1;font:Tokens.font.body.medium}
                    StyledText {
                        Layout.fillWidth:true;elide:Text.ElideRight;maximumLineCount:1;font:Tokens.font.body.small;color:Colours.palette.m3onSurfaceVariant
                        text:row.modelData.pending?Tr.tr("Connecting"):row.modelData.active?Tr.tr("Connected"):row.modelData.kind==="vpn"?Tr.tr("VPN"):row.modelData.kind==="ethernet"?Tr.tr("Ethernet"):row.modelData.data.isSecure?Tr.tr("Secured"):Tr.tr("Open network")
                    }
                }
                MaterialIcon {text:row.modelData.pending?"sync":row.modelData.active?"link_off":"link";color:row.modelData.active?Colours.palette.m3primary:Colours.palette.m3onSurfaceVariant}
            }
        }
    }
    StyledText {visible:root.connectionRows.length===0;Layout.fillWidth:true;text:Tr.tr("No connections available");wrapMode:Text.WordWrap;font:Tokens.font.body.small;color:Colours.palette.m3onSurfaceVariant}
    StyledText {
        Layout.fillWidth:true;visible:text.length>0
        text:root.vpnBackend.error||Nmcli.lastError
        color:Colours.palette.m3error;font:Tokens.font.body.small;wrapMode:Text.Wrap;maximumLineCount:2;elide:Text.ElideRight;textFormat:Text.PlainText
    }
    RowButton {first:true;last:true;objectName:"networkSettingsRow";text:Tr.tr("Network settings");icon:"settings";onClicked:root.openSettings()}
    Connections {
        target:Nmcli
        function onActiveChanged():void {
            if(Nmcli.active?.ssid===root.connectingToSsid)root.connectingToSsid="";
            if(root.showPasswordDialog&&Nmcli.active?.ssid===root.passwordNetwork?.ssid){root.showPasswordDialog=false;root.passwordNetwork=null;if(root.popouts.currentName==="wirelesspassword")root.popouts.currentName="network";}
        }
        function onConnectionFailed(ssid):void {if(root.connectingToSsid===ssid)root.connectingToSsid=""}
    }
    Connections {
        target:root.popouts
        function onCurrentNameChanged():void {if(root.popouts.currentName!=="wirelesspassword"&&root.showPasswordDialog){root.showPasswordDialog=false;root.passwordNetwork=null;}}
    }
}
