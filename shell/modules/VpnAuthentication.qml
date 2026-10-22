pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import Quickshell
import Hyprstack.Config
import Hyprstack.I18n
import Hyprstack.Services
import qs.services
import qs.components
import qs.components.controls
import qs.modules.nexus.common
FloatingWindow {
    id:root
    property var agent:VpnSecretAgent
    visible:!!root.agent.challenge.name
    title:Tr.tr("VPN authentication")
    implicitWidth:480
    implicitHeight:content.implicitHeight+40
    color:Colours.palette.m3surface
    property var credentials:({})
    property string challengeId
    function syncChallenge():void {
        const challenge=root.agent.challenge;
        if(!challenge.name){credentials=({});challengeId="";return;}
        const next=String(challenge.requestId??challenge.name);
        if(next===challengeId)return;
        challengeId=next;
        const initial=Object.assign({},challenge.values??({}));
        for(const field of challenge.fields??[])initial[field.key]=field.value??"";
        credentials=initial;remember.checked=false;
    }
    onVisibleChanged:if(visible)Qt.callLater(syncChallenge)
    Component.onCompleted:syncChallenge()
    onClosed:root.agent.cancel()
    Connections {target:root.agent;function onChanged():void{root.syncChallenge()}}
    ColumnLayout {
        id:content
        anchors.left:parent.left;anchors.right:parent.right;anchors.top:parent.top;anchors.margins:20
        spacing:Tokens.spacing.small
        StyledText {text:root.agent.challenge.name??"";font:Tokens.font.title.large}
        StyledText {text:root.agent.challenge.prompt??Tr.tr("Enter VPN credentials");wrapMode:Text.WordWrap;Layout.fillWidth:true}
        FeatureError {error:root.agent.error}
        Repeater {
            model:root.agent.challenge.fields??[]
            VpnPasswordField {
                required property var modelData
                Layout.fillWidth:true
                label:Tr.tr(modelData.label)
                value:root.credentials[modelData.key]??modelData.value??""
                secret:modelData.secret!==false
                onValueEdited:v=>root.credentials=Object.assign({},root.credentials,{[modelData.key]:v})
            }
        }
        ToggleRow {id:remember;text:Tr.tr("Remember in system keyring");checked:false}
        RowButton {first:true;text:Tr.tr("Connect");icon:"vpn_key";onClicked:root.agent.submit(root.credentials,remember.checked)}
        RowButton {last:true;text:Tr.tr("Cancel");icon:"close";onClicked:root.agent.cancel()}
    }
}
