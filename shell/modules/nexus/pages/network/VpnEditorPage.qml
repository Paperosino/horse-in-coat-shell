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
    title:Tr.tr("VPN connection")
    property var form:({})
    property var protocol:({})
    property bool dirty:false
    property bool advanced:false
    property string jsonError
    property string localError
    property string fileKey
    function load():void {
        if(dirty)return;
        form=JSON.parse(JSON.stringify(NetworkManagerVpn.draft));
        protocol=NetworkManagerVpn.plugins.find(p=>p.service===form.type)??({fields:[]});
        advanced=!(protocol.fields??[]).length&&form.type!=="wireguard";
    }
    function set(key,value):void { form=Object.assign({},form,{[key]:value});dirty=true;localError="" }
    function nested(group,key,value):void { set(group,Object.assign({},form[group]??({}),{[key]:value})) }
    function save():void {
        if(jsonError)return;
        const missing=(protocol.fields??[]).find(f=>f.required&&!String(form.data?.[f.key]??"").trim());
        if(missing){localError=Tr.tr(missing.label)+": "+Tr.tr("A value is required");return}
        localError="";NetworkManagerVpn.save(form)
    }
    Component.onCompleted:load()
    readonly property Connections vpnConnections: Connections {
        target:NetworkManagerVpn
        function onDraftChanged():void {root.load()}
        function onSaved():void {root.dirty=false;root.nState.closeSubPage()}
    }
    readonly property FileDialog certificateDialog: FileDialog { id:picker;title:Tr.tr("Select certificate or key file");onAccepted:root.nested("data",root.fileKey,decodeURIComponent(selectedFile.toString().replace(/^file:\/\//,""))) }
    ColumnLayout {
        width:root.cappedWidth;anchors.horizontalCenter:parent.horizontalCenter;spacing:Tokens.spacing.extraSmall/2
        InfoRow { first:true;last:true;label:Tr.tr("Protocol");value:root.protocol.name??root.form.type??"" }
        InfoRow {first:true;last:true;label:Tr.tr("Saved settings");value:Tr.tr("Changes apply the next time you connect.")}
        FeatureError { error:root.localError||root.jsonError||NetworkManagerVpn.error }
        TextFieldRow { label:Tr.tr("Connection name");value:root.form.name??"";onValueEdited:v=>root.set("name",v) }
        TextFieldRow { label:Tr.tr("Interface name");subtext:Tr.tr("Optional except for a new WireGuard interface");value:root.form.interface??"";onValueEdited:v=>root.set("interface",v) }
        ToggleRow { visible:root.form.type==="wireguard";text:Tr.tr("Connect automatically");checked:!!root.form.autoconnect;onToggled:v=>root.set("autoconnect",v) }
        SectionHeader { text:Tr.tr("Authentication and tunnel") }
        Repeater {
            model:root.protocol.fields??[]
            ColumnLayout {
                id:field
                required property var modelData
                required property int index
                Layout.fillWidth:true;spacing:Tokens.spacing.extraSmall/2
                SectionHeader { visible:!!field.modelData.section&&(field.index===0||root.protocol.fields[field.index-1].section!==field.modelData.section);text:field.modelData.section??"" }
                Loader {
                    Layout.fillWidth:true
                    sourceComponent:field.modelData.type==="secret"?secret:field.modelData.type==="file"?file:normal
                    Component {
                        id:normal
                        GenericSettingRow {
                            spec:field.modelData
                            value:field.modelData.type==="bool"?root.form.data?.[field.modelData.key]==="yes":(root.form.data?.[field.modelData.key]??"")
                            onEdited:v=>root.nested("data",field.modelData.key,field.modelData.type==="bool"?(v?"yes":"no"):String(v))
                        }
                    }
                    Component {
                        id:secret
                        TextFieldRow {
                            label:Tr.tr(field.modelData.label)
                            subtext:Tr.tr("Leave empty to keep the stored credential")
                            value:root.form.secrets?.[field.modelData.key]??""
                            field.echoMode:TextInput.Password
                            onValueEdited:v=>root.nested("secrets",field.modelData.key,v)
                        }
                    }
                    Component {
                        id:file
                        ColumnLayout {
                            TextFieldRow { label:Tr.tr(field.modelData.label);value:root.form.data?.[field.modelData.key]??"";onValueEdited:v=>root.nested("data",field.modelData.key,v) }
                            RowButton { text:Tr.tr("Choose file");icon:"folder_open";onClicked:{root.fileKey=field.modelData.key;picker.open()} }
                        }
                    }
                }
            }
        }
        ColumnLayout {
            visible:root.form.type==="wireguard";Layout.fillWidth:true;spacing:Tokens.spacing.extraSmall/2
            TextFieldRow { label:Tr.tr("WireGuard private key");subtext:Tr.tr("Leave empty to keep the stored credential");value:root.form.secrets?.["private-key"]??"";field.echoMode:TextInput.Password;onValueEdited:v=>root.nested("secrets","private-key",v) }
            RowButton {text:Tr.tr("Generate private key");icon:"key";onClicked:root.nested("secrets","private-key",NetworkManagerVpn.generateWireGuardKey())}
            GenericSettingRow { spec:({label:"Listen port",type:"int",min:0,max:65535});value:root.form.wireguard?.listenPort??0;onEdited:v=>root.nested("wireguard","listenPort",v) }
            GenericSettingRow { spec:({label:"MTU",type:"int",min:0,max:65535});value:root.form.wireguard?.mtu??0;onEdited:v=>root.nested("wireguard","mtu",v) }
            TextFieldRow {label:"FwMark";value:String(root.form.wireguard?.fwmark??0);onValueEdited:v=>root.nested("wireguard","fwmark",Number(v))}
            ToggleRow {text:Tr.tr("Create routes from allowed IPs");checked:root.form.wireguard?.peerRoutes??true;onToggled:v=>root.nested("wireguard","peerRoutes",v)}
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
                    TextFieldRow {label:Tr.tr("Pre-shared key");value:peer.modelData.presharedKey??"";field.echoMode:TextInput.Password;onEditingFinished:v=>peer.change("presharedKey",v)}
                    GenericSettingRow {spec:({label:"Persistent keepalive",type:"int",min:0,max:65535});value:peer.modelData.keepalive??0;onEdited:v=>peer.change("keepalive",v)}
                    RowButton {text:Tr.tr("Remove peer");icon:"remove";onClicked:{const peers=(root.form.wireguard?.peers??[]).slice();peers.splice(peer.index,1);root.nested("wireguard","peers",peers)}}
                }
            }
            RowButton {text:Tr.tr("Add peer");icon:"add";onClicked:root.nested("wireguard","peers",[...(root.form.wireguard?.peers??[]),{publicKey:"",endpoint:"",allowedIPs:"",keepalive:0}])}
        }
        VpnIpSettings { settings:root.form.ip4??({});onEdited:(k,v)=>root.nested("ip4",k,v) }
        VpnIpSettings { ipv6:true;settings:root.form.ip6??({});onEdited:(k,v)=>root.nested("ip6",k,v) }
        ToggleRow {visible:root.form.type!=="wireguard";text:Tr.tr("Advanced plugin properties");checked:root.advanced;onToggled:v=>root.advanced=v}
        VpnTextArea {
            visible:root.advanced&&root.form.type!=="wireguard"
            label:"Plugin data (JSON)";hint:"All plugin-specific keys are preserved. Edit the dictionary for options not shown above."
            value:JSON.stringify(root.form.data??({}),null,2)
            onEdited:v=>{try{const data=JSON.parse(v);if(data&&typeof data==="object"&&!Array.isArray(data)){root.set("data",data);root.jsonError=""}else root.jsonError=Tr.tr("Expected a JSON object")}catch(e){root.jsonError=Tr.tr("Invalid JSON")}}
        }
        RowButton {first:true;text:Tr.tr("Save connection");icon:"save";disabled:NetworkManagerVpn.busy||!root.form.name?.trim()||!!root.jsonError;onClicked:root.save()}
        RowButton {last:true;text:Tr.tr("Cancel");icon:"close";disabled:NetworkManagerVpn.busy;onClicked:{NetworkManagerVpn.discard();root.nState.closeSubPage()}}
    }
}
