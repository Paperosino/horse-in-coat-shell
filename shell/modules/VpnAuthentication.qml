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
    visible:!!VpnSecretAgent.challenge.name
    title:Tr.tr("VPN authentication")
    implicitWidth:480
    implicitHeight:content.implicitHeight+40
    color:Colours.palette.m3surface
    property var credentials:({})
    onVisibleChanged:if(visible){credentials=({});remember.checked=false}
    onClosed:VpnSecretAgent.cancel()
    Connections {target:VpnSecretAgent;function onChanged():void{if(!VpnSecretAgent.challenge.name)root.credentials=({})}}
    ColumnLayout {
        id:content
        anchors.left:parent.left;anchors.right:parent.right;anchors.top:parent.top;anchors.margins:20
        spacing:Tokens.spacing.small
        StyledText {text:VpnSecretAgent.challenge.name??"";font:Tokens.font.title.large}
        StyledText {text:VpnSecretAgent.challenge.prompt??Tr.tr("Enter VPN credentials");wrapMode:Text.WordWrap;Layout.fillWidth:true}
        FeatureError {error:VpnSecretAgent.error}
        Repeater {
            model:VpnSecretAgent.challenge.fields??[]
            StyledTextField {
                required property var modelData
                Layout.fillWidth:true
                placeholderText:modelData.label
                echoMode:modelData.secret===false?TextInput.Normal:TextInput.Password
                onTextEdited:root.credentials=Object.assign({},root.credentials,{[modelData.key]:text})
            }
        }
        ToggleRow {id:remember;text:Tr.tr("Remember in system keyring");checked:false}
        RowButton {first:true;text:Tr.tr("Connect");icon:"vpn_key";onClicked:VpnSecretAgent.submit(root.credentials,remember.checked)}
        RowButton {last:true;text:Tr.tr("Cancel");icon:"close";onClicked:VpnSecretAgent.cancel()}
    }
}
