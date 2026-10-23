pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import Hyprstack.Config
import qs.components
import qs.services

ConnectedRect {
    id: root

    property alias icon: iconLabel.text
    property alias text: label.text
    property alias subtext: subLabel.text
    property string trailingIcon
    property alias disabled: stateLayer.disabled

    readonly property alias iconLabel: iconLabel
    readonly property alias label: label
    readonly property alias subLabel: subLabel

    signal clicked(event: MouseEvent)

    Layout.fillWidth: true
    implicitHeight: row.implicitHeight + Tokens.padding.medium * 2

    StateLayer {
        id: stateLayer
        keyboardFocusable: true

        onClicked: e => root.clicked(e)
    }

    RowLayout {
        id: row

        anchors.left: parent.left
        anchors.right: parent.right
        anchors.verticalCenter: parent.verticalCenter
        anchors.margins: Tokens.padding.largeIncreased

        spacing: Tokens.spacing.medium
        opacity: root.disabled ? 0.5 : 1

        Behavior on opacity {
            Anim {}
        }

        MaterialIcon {
            id: iconLabel

            color: Colours.palette.m3onSurfaceVariant
            fontStyle: Tokens.font.icon.medium
            fill: 1
        }

        Column {
            id: column

            Layout.fillWidth: true
            Layout.minimumWidth: 0
            spacing: 3 * Tokens.scale

            StyledText {
                id: label

                anchors.left: parent.left
                anchors.right: parent.right

                font: Tokens.font.body.medium
                wrapMode: Text.WrapAtWordBoundaryOrAnywhere
            }

            StyledText {
                id: subLabel

                anchors.left: parent.left
                anchors.right: parent.right

                visible: text
                color: Colours.palette.m3onSurfaceVariant
                font: Tokens.font.body.small
                wrapMode: Text.WrapAtWordBoundaryOrAnywhere
            }
        }

        Loader {
            asynchronous: true
            active: root.trailingIcon
            visible: active

            sourceComponent: MaterialIcon {
                text: root.trailingIcon
                color: Colours.palette.m3onSurfaceVariant
                fontStyle: Tokens.font.icon.medium
            }
        }
    }
}
