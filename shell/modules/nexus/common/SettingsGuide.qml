pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import Hyprstack.Config
import qs.components
import qs.services
StyledRect {
    id: root
    property string icon: "palette"
    property string title
    property string description
    property list<string> badges: []
    Layout.fillWidth: true
    implicitHeight: content.implicitHeight + Tokens.padding.large * 2
    radius: Tokens.rounding.extraLarge
    color: Colours.palette.m3secondaryContainer
    ColumnLayout {
        id: content
        anchors { left:parent.left;right:parent.right;top:parent.top;margins:Tokens.padding.large }
        spacing: Tokens.spacing.medium
        RowLayout {
            Layout.fillWidth: true
            spacing: Tokens.spacing.large
            MaterialIcon { text:root.icon; fontStyle:Tokens.font.icon.extraLarge; color:Colours.palette.m3onSecondaryContainer }
            ColumnLayout {
                Layout.fillWidth:true
                StyledText { Layout.fillWidth:true;text:root.title;font:Tokens.font.title.medium;wrapMode:Text.WordWrap;color:Colours.palette.m3onSecondaryContainer }
                StyledText { Layout.fillWidth:true;text:root.description;font:Tokens.font.body.small;wrapMode:Text.WordWrap;color:Colours.palette.m3onSecondaryContainer }
            }
        }
        Flow {
            Layout.fillWidth:true
            spacing:Tokens.spacing.small
            Repeater {
                model:root.badges
                delegate: StyledRect {
                    required property string modelData
                    implicitWidth:badge.implicitWidth+Tokens.padding.medium*2
                    implicitHeight:badge.implicitHeight+Tokens.padding.small*2
                    color:Colours.palette.m3surfaceContainerHigh
                    radius:Tokens.rounding.full
                    StyledText { id:badge;anchors.centerIn:parent;text:parent.modelData;font:Tokens.font.label.small }
                }
            }
        }
    }
}
