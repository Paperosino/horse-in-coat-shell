pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import Hyprstack.Config
import qs.components
import qs.services
import qs.modules.nexus.common

ConnectedRect {
    id: root

    property alias label: label.text
    property string subtext
    property alias value: value.text
    property string icon
    property color iconColour: Colours.palette.m3onSurfaceVariant
    property Component leadingComponent: icon ? iconComp : null

    Layout.fillWidth: true
    implicitHeight: rowLayout.implicitHeight + rowLayout.anchors.margins * 2

    Component {
        id: iconComp

        MaterialIcon {
            text: root.icon
            color: root.iconColour
            fontStyle: Tokens.font.icon.small
        }
    }

    RowLayout {
        id: rowLayout

        anchors.fill: parent
        anchors.margins: Tokens.padding.medium
        anchors.leftMargin: Tokens.padding.largeIncreased
        anchors.rightMargin: Tokens.padding.largeIncreased
        spacing: Tokens.spacing.medium

        Loader {
            visible: root.leadingComponent
            active: root.leadingComponent
            sourceComponent: root.leadingComponent
        }

        ColumnLayout {
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            spacing: 3 * Tokens.scale

            StyledText {
                id: label

                Layout.fillWidth: true
                font: Tokens.font.body.medium
                Layout.minimumWidth: 0
                wrapMode: Text.WrapAtWordBoundaryOrAnywhere
            }

            StyledText {
                Layout.fillWidth: true
                visible: root.subtext
                text: root.subtext
                color: Colours.palette.m3onSurfaceVariant
                font: Tokens.font.body.small
                Layout.minimumWidth: 0
                wrapMode: Text.WrapAtWordBoundaryOrAnywhere
            }
        }

        StyledText {
            id: value

            Layout.maximumWidth: root.width / 2
            Layout.minimumWidth: 0
            horizontalAlignment: Text.AlignRight
            color: Colours.palette.m3onSurfaceVariant
            font: Tokens.font.body.medium
            wrapMode: Text.WrapAtWordBoundaryOrAnywhere
        }
    }
}
