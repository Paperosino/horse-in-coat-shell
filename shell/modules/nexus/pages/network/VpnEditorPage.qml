pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import QtQuick.Dialogs
import Hyprstack.Config
import Hyprstack.I18n
import Hyprstack.Services
import qs.modules.nexus.common
import "../../../../utils/scripts/vpn-editor.js" as EditorPolicy
PageBase {
    id:root
    title:Tr.tr("VPN connection")
    property var vpnBackend:NetworkManagerVpn
    property var form:({})
    property var protocol:({})
    readonly property string policyKey:JSON.stringify({type:form.type??"",data:{"connection-type":form.data?.["connection-type"],"user-auth-type":form.data?.["user-auth-type"],"machine-auth-type":form.data?.["machine-auth-type"],"ipsec-enabled":form.data?.["ipsec-enabled"],method:form.data?.method}})
    readonly property var basicFields:{const p=JSON.parse(policyKey);return (protocol.fields??[]).filter(f=>EditorPolicy.fieldVisible(p.type,f,p.data,false))}
    readonly property var advancedFields:{const p=JSON.parse(policyKey);return (protocol.fields??[]).filter(f=>EditorPolicy.fieldVisible(p.type,f,p.data,true))}
    property string pendingProtocol:""
    property var protocolDrafts:({})
    readonly property var selectedPlugin:root.vpnBackend.plugins.find(p=>p.service===(root.pendingProtocol||root.form.type))??({})
    readonly property bool connected:root.vpnBackend.profiles.some(p=>p.path===root.form.path&&p.active)
    function requestProtocol(type):void {
        if(type===form.type)return;
        pendingProtocol=type;
    }
    function applyProtocol():void {
        if(!pendingProtocol||!selectedPlugin.installed||connected)return;
        protocolDrafts[form.type]=JSON.parse(JSON.stringify(form));
        const next=protocolDrafts[pendingProtocol]??EditorPolicy.changeProtocol(form,pendingProtocol);
        // Shared profile identity follows the latest edits.
        form=Object.assign({},next,{path:form.path,uuid:form.uuid,name:form.name});
        protocol=root.vpnBackend.plugins.find(p=>p.service===form.type)??({fields:[]});
        pendingProtocol="";dirty=true;jsonError="";localError="";
    }
    property bool dirty:false
    property bool advanced:false
    property bool pluginData:false
    readonly property bool wireguard:form.type==="wireguard"
    property string jsonError
    property string localError
    property bool deleting:false
    property bool confirmDelete:false
    property string fileKey
    function load():void {
        if(dirty)return;
        form=JSON.parse(JSON.stringify(root.vpnBackend.draft));
        protocol=root.vpnBackend.plugins.find(p=>p.service===form.type)??({fields:[]});
        if(!form.path&&!form.importToken)form=Object.assign({},form,{data:Object.assign({},EditorPolicy.defaults(form.type),form.data??({}))});
        advanced=false;pluginData=false;
    }
    function set(key,value):void { form=Object.assign({},form,{[key]:value});dirty=true;localError="" }
    function nested(group,key,value):void { set(group,Object.assign({},form[group]??({}),{[key]:value})) }
    function save():void {
        if(jsonError)return;
        const missing=(protocol.fields??[]).find(f=>f.required&&!String(form.data?.[f.key]??"").trim());
        if(missing){localError=Tr.tr(missing.label)+": "+Tr.tr("A value is required");return}
        if(pendingProtocol){localError=Tr.tr("Confirm or cancel the VPN type change first");return}
        localError="";root.vpnBackend.save(form)
    }
    Component.onCompleted:load()
    readonly property Connections vpnConnections: Connections {
        target:root.vpnBackend
        function onDraftChanged():void {root.load()}
        function onOperationSucceeded():void {if(root.deleting){root.deleting=false;root.vpnBackend.discard();root.nState.closeSubPage()}}
        function onChanged():void {if(!root.vpnBackend.busy&&root.vpnBackend.error)root.deleting=false}
        function onSaved():void {root.dirty=false;root.nState.closeSubPage()}
    }
    readonly property FileDialog exportDialog:FileDialog {id:exporter;title:Tr.tr("Export VPN configuration");fileMode:FileDialog.SaveFile;nameFilters:["NetworkManager (*.nmconnection)","VPN configuration (*.conf *.ovpn)"];defaultSuffix:"nmconnection";onAccepted:root.vpnBackend.exportFile(root.form.path,selectedFile)}
    readonly property FileDialog certificateDialog: FileDialog { id:picker;title:Tr.tr("Select certificate or key file");onAccepted:root.nested("data",root.fileKey,decodeURIComponent(selectedFile.toString().replace(/^file:\/\//,""))) }
    ColumnLayout {
        width:root.cappedWidth;anchors.horizontalCenter:parent.horizontalCenter;spacing:Tokens.spacing.extraSmall/2
        GenericSettingRow {
            objectName:"vpnProtocolSelector"
            spec:({label:"VPN type",type:"choice",choices:root.vpnBackend.plugins.map(p=>({label:p.name+(p.installed?"":" · "+Tr.tr("Not installed")),value:p.service}))})
            value:root.form.type
            onEdited:v=>root.requestProtocol(v)
        }
        InfoRow {visible:root.connected;first:true;last:true;label:Tr.tr("VPN type");value:Tr.tr("Disconnect the VPN before changing its protocol")}
        InfoRow {visible:!!root.pendingProtocol;first:true;last:true;label:Tr.tr("Change VPN type");value:Tr.tr("The server address and username are copied where compatible. Enter credentials for the new protocol; the saved connection changes only after saving.")}
        RowButton {objectName:"vpnInstallSelectedPlugin";visible:!!root.pendingProtocol&&!root.selectedPlugin.installed&&!!root.selectedPlugin.package;text:Tr.tr("Install plugin")+" · "+(root.selectedPlugin.package??"");icon:"download";disabled:root.vpnBackend.busy;onClicked:root.vpnBackend.installPlugin(root.selectedPlugin.id)}
        RowButton {objectName:"vpnConfirmProtocolChange";visible:!!root.pendingProtocol;text:Tr.tr("Use selected VPN type")+" · "+(root.selectedPlugin.name??"");icon:"swap_horiz";disabled:root.vpnBackend.busy||!root.selectedPlugin.installed||root.connected;onClicked:root.applyProtocol()}
        RowButton {visible:!!root.pendingProtocol;text:Tr.tr("Cancel");icon:"close";onClicked:root.pendingProtocol=""}
        FeatureError { error:root.localError||root.jsonError||root.vpnBackend.error }
        TextFieldRow { label:Tr.tr("Connection name");value:root.form.name??"";onValueEdited:v=>root.set("name",v) }
        TextFieldRow { visible:root.wireguard||root.advanced;label:Tr.tr("Interface name");subtext:Tr.tr("Optional except for a new WireGuard interface");value:root.form.interface??"";onValueEdited:v=>root.set("interface",v) }
        ToggleRow { visible:root.form.type==="wireguard";text:Tr.tr("Connect automatically");checked:!!root.form.autoconnect;onToggled:v=>root.set("autoconnect",v) }

        Repeater {
            model:root.basicFields
            VpnProtocolField {
                required property var modelData
                required property int index
                showSection:index===0||root.basicFields[index-1]?.section!==modelData.section
                spec:modelData;settings:root.form.data??({});credentials:root.form.secrets??({})
                onEdited:(k,v)=>root.nested("data",k,v)
                onCredentialEdited:(k,v)=>root.nested("secrets",k,v)
                onFileRequested:k=>{root.fileKey=k;picker.open()}
            }
        }

        VpnTextArea {visible:root.wireguard;label:"IPv4 addresses";hint:"One address/prefix per line";value:root.form.ip4?.addresses??"";onEdited:v=>root.nested("ip4","addresses",v)}
        VpnTextArea {visible:root.wireguard;label:"IPv6 addresses";hint:"One address/prefix per line";value:root.form.ip6?.addresses??"";onEdited:v=>{root.nested("ip6","addresses",v);root.nested("ip6","method",v.trim()?"manual":"disabled")}}
        ColumnLayout {
            visible:root.form.type==="wireguard";Layout.fillWidth:true;spacing:Tokens.spacing.extraSmall/2
            VpnPasswordField { label:Tr.tr("WireGuard private key");subtext:Tr.tr("Leave empty to keep the stored credential");value:root.form.secrets?.["private-key"]??"";onValueEdited:v=>root.nested("secrets","private-key",v) }
            RowButton {text:Tr.tr("Generate private key");icon:"key";onClicked:root.nested("secrets","private-key",root.vpnBackend.generateWireGuardKey())}
            Repeater {
                model:root.form.wireguard?.peers?.length??0
                ColumnLayout {
                    id:peer
                    required property int index
                    readonly property var modelData:root.form.wireguard?.peers[index]??({})
                    Layout.fillWidth:true;spacing:Tokens.spacing.extraSmall/2
                    function change(key,value):void {const peers=(root.form.wireguard?.peers??[]).slice();peers[index]=Object.assign({},modelData,{[key]:value});root.nested("wireguard","peers",peers)}
                    SectionHeader {text:Tr.tr("WireGuard peer")+" "+(index+1)}
                    TextFieldRow {label:Tr.tr("Public key");value:peer.modelData.publicKey??"";onEditingFinished:v=>peer.change("publicKey",v)}
                    TextFieldRow {label:Tr.tr("Endpoint");value:peer.modelData.endpoint??"";onEditingFinished:v=>peer.change("endpoint",v)}
                    TextFieldRow {label:Tr.tr("Allowed IPs");value:peer.modelData.allowedIPs??"";onEditingFinished:v=>peer.change("allowedIPs",v)}
                    RowButton {text:Tr.tr("Remove peer");icon:"remove";onClicked:{const peers=(root.form.wireguard?.peers??[]).slice();peers.splice(peer.index,1);root.nested("wireguard","peers",peers)}}
                }
            }
            RowButton {text:Tr.tr("Add peer");icon:"add";onClicked:root.nested("wireguard","peers",[...(root.form.wireguard?.peers??[]),{publicKey:"",endpoint:"",allowedIPs:"",keepalive:0}])}
        }
        RowButton {
            objectName:"vpnAdvancedToggle";first:true;last:true
            text:Tr.tr("Advanced settings");icon:"tune";trailingIcon:root.advanced?"expand_less":"expand_more"
            onClicked:root.advanced=!root.advanced
        }
        ColumnLayout {
            objectName:"vpnAdvancedSettings";visible:root.advanced;Layout.fillWidth:true;spacing:Tokens.spacing.extraSmall/2
            ColumnLayout {
                visible:root.wireguard;Layout.fillWidth:true;spacing:Tokens.spacing.extraSmall/2
            GenericSettingRow { spec:({label:"Listen port",type:"int",min:0,max:65535});value:root.form.wireguard?.listenPort??0;onEdited:v=>root.nested("wireguard","listenPort",v) }
            GenericSettingRow { spec:({label:"MTU",type:"int",min:0,max:65535});value:root.form.wireguard?.mtu??0;onEdited:v=>root.nested("wireguard","mtu",v) }
            TextFieldRow {label:"FwMark";value:String(root.form.wireguard?.fwmark??0);onValueEdited:v=>root.nested("wireguard","fwmark",Number(v))}
            ToggleRow {text:Tr.tr("Create routes from allowed IPs");checked:root.form.wireguard?.peerRoutes??true;onToggled:v=>root.nested("wireguard","peerRoutes",v)}
                Repeater {
                    model:root.form.wireguard?.peers?.length??0
                    ColumnLayout {
                        id:advancedPeer
                        required property int index
                        readonly property var modelData:root.form.wireguard?.peers[index]??({})
                        Layout.fillWidth:true;spacing:Tokens.spacing.extraSmall/2
                        function change(key,value):void {const peers=(root.form.wireguard?.peers??[]).slice();peers[index]=Object.assign({},modelData,{[key]:value});root.nested("wireguard","peers",peers)}
                        SectionHeader {text:Tr.tr("WireGuard peer")+" "+(index+1)}
                    VpnPasswordField {label:Tr.tr("Pre-shared key");value:advancedPeer.modelData.presharedKey??"";onEditingFinished:v=>advancedPeer.change("presharedKey",v)}
                    GenericSettingRow {spec:({label:"Persistent keepalive",type:"int",min:0,max:65535});value:advancedPeer.modelData.keepalive??0;onEdited:v=>advancedPeer.change("keepalive",v)}
                    }
                }
            }
            Repeater {
                model:root.advanced?root.advancedFields:[]
                VpnProtocolField {
                    required property var modelData
                    required property int index
                    spec:modelData;settings:root.form.data??({});credentials:root.form.secrets??({})
                    showSection:index===0||root.advancedFields[index-1]?.section!==modelData.section
                    onEdited:(k,v)=>root.nested("data",k,v)
                    onCredentialEdited:(k,v)=>root.nested("secrets",k,v)
                    onFileRequested:k=>{root.fileKey=k;picker.open()}
                }
            }
            VpnIpSettings {settings:root.form.ip4??({});onEdited:(k,v)=>root.nested("ip4",k,v)}
            VpnIpSettings {ipv6:true;settings:root.form.ip6??({});onEdited:(k,v)=>root.nested("ip6",k,v)}
            RowButton {visible:!!root.form.path;text:Tr.tr("Export configuration");subtext:Tr.tr("The export contains private credentials. Keep it secure.");icon:"file_save";disabled:root.vpnBackend.busy;onClicked:exporter.open()}
            RowButton {visible:!!root.form.path;text:Tr.tr("Delete connection");icon:"delete";disabled:root.vpnBackend.busy;onClicked:root.confirmDelete=!root.confirmDelete}
            RowButton {visible:root.confirmDelete;text:Tr.tr("Confirm deletion");icon:"delete_forever";disabled:root.vpnBackend.busy;onClicked:{root.deleting=true;root.vpnBackend.remove(root.form.path)}}
            ToggleRow {visible:!root.wireguard;text:Tr.tr("Advanced plugin properties");checked:root.pluginData;onToggled:v=>root.pluginData=v}
        }
        VpnTextArea {
            visible:root.advanced&&root.pluginData&&!root.wireguard
            label:"Plugin data (JSON)";hint:"All plugin-specific keys are preserved. Edit the dictionary for options not shown above."
            value:JSON.stringify(root.form.data??({}),null,2)
            onEdited:v=>{try{const data=JSON.parse(v);if(data&&typeof data==="object"&&!Array.isArray(data)){root.set("data",data);root.jsonError=""}else root.jsonError=Tr.tr("Expected a JSON object")}catch(e){root.jsonError=Tr.tr("Invalid JSON")}}
        }
        RowButton {first:true;text:Tr.tr("Save connection");icon:"save";disabled:root.vpnBackend.busy||!root.form.name?.trim()||!!root.jsonError;onClicked:root.save()}
        RowButton {last:true;text:Tr.tr("Cancel");icon:"close";disabled:root.vpnBackend.busy;onClicked:{root.vpnBackend.discard();root.nState.closeSubPage()}}
    }
}
