pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import Hyprstack.Config
import qs.components
import qs.services

ConnectedRect {
    id:root
    property string title
    property string description
    property string icon:"tune"
    property string badge
    default property alias contents:body.data
    Layout.fillWidth:true
    first:true;last:true
    implicitHeight:frame.implicitHeight+Tokens.padding.large*2
    readonly property ColumnLayout frame:ColumnLayout {
        parent:root
        anchors.left:parent.left;anchors.right:parent.right;anchors.top:parent.top
        anchors.margins:Tokens.padding.large
        spacing:Tokens.spacing.medium
        RowLayout {
            Layout.fillWidth:true;spacing:Tokens.spacing.medium
            StyledRect {
                implicitWidth:48*Tokens.scale;implicitHeight:48*Tokens.scale
                radius:Tokens.rounding.large;color:Colours.palette.m3secondaryContainer
                MaterialIcon {anchors.centerIn:parent;text:root.icon;color:Colours.palette.m3onSecondaryContainer;fontStyle:Tokens.font.icon.medium}
            }
            ColumnLayout {
                Layout.fillWidth:true;spacing:4
                StyledText {Layout.fillWidth:true;text:root.title;font:Tokens.font.title.medium;wrapMode:Text.WordWrap}
                StyledText {Layout.fillWidth:true;visible:!!root.description;text:root.description;font:Tokens.font.body.small;color:Colours.palette.m3onSurfaceVariant;wrapMode:Text.WordWrap}
            }
            StyledRect {
                visible:!!root.badge;implicitWidth:badgeText.implicitWidth+20;implicitHeight:badgeText.implicitHeight+10
                radius:Tokens.rounding.full;color:Colours.palette.m3surfaceContainerHigh
                StyledText {id:badgeText;anchors.centerIn:parent;text:root.badge;font:Tokens.font.label.small;color:Colours.palette.m3primary}
            }
        }
        ColumnLayout {id:body;Layout.fillWidth:true;spacing:Tokens.spacing.extraSmall}
    }
}
