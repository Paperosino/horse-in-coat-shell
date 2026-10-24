pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import Hyprstack.Config
import qs.components
import qs.components.controls
import qs.services
Item {
    id:root
    required property var pluginApi
    required property string slot
    implicitWidth:(slot==="barWidget"?120:260)*Tokens.scale
    implicitHeight: content.implicitHeight
    Column {
    id: content
    width: root.width
    spacing:Tokens.spacing.small
    Repeater {
        model:root.pluginApi?.isolatedState?.slots?.[root.slot]??[]
        delegate:Loader {
            id:part
            required property var modelData
            width:root.width
            sourceComponent:modelData.type==="button"?button:modelData.type==="toggle"?toggle:modelData.type==="progress"?progress:label
            Component {
                id:label
                StyledText {text:part.modelData.text??"";textFormat:Text.PlainText;wrapMode:Text.WordWrap;font:part.modelData.type==="heading"?Tokens.font.title.small:Tokens.font.body.medium}
            }
            Component {
                id:button
                IconTextButton {
                    text:part.modelData.text??"";icon:part.modelData.icon||"extension";label.textFormat:Text.PlainText
                    disabled:part.modelData.enabled===false
                    onClicked:root.pluginApi.sendAction(part.modelData.id??"",null)
                }
            }
            Component {
                id:toggle
                RowLayout {
                    StyledText {Layout.fillWidth:true;text:part.modelData.text??"";textFormat:Text.PlainText;wrapMode:Text.WordWrap}
                    StyledSwitch {checked:part.modelData.value??false;disabled:part.modelData.enabled===false;Accessible.name:part.modelData.text??"";onToggled:root.pluginApi.sendAction(part.modelData.id??"",checked)}
                }
            }
            Component {
                id:progress
                Column {
                    spacing:Tokens.spacing.extraSmall
                    StyledText {text:part.modelData.text??"";textFormat:Text.PlainText}
                    Rectangle {
                        width:part.width;height:6*Tokens.scale;radius:height/2;color:Colours.palette.m3surfaceContainerHighest
                        Rectangle {width:parent.width*(part.modelData.value??0);height:parent.height;radius:height/2;color:Colours.palette.m3primary}
                    }
                }
            }
        }
    }
}
}
