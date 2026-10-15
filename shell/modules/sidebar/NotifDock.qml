pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import Quickshell.Widgets
import Hyprstack.Config
import Hyprstack.I18n
import qs.components
import qs.components.containers
import qs.components.controls
import qs.services

Item {
    id: root

    required property Props props
    required property ScreenState screenState
    readonly property int notifCount: Notifs.notClosed.length

    anchors.fill: parent
    anchors.margins: Tokens.padding.medium

    ColumnLayout {
        id: header

        anchors.top: parent.top
        anchors.left: parent.left
        anchors.right: parent.right
        spacing: Tokens.spacing.small

        RowLayout {
            Layout.fillWidth: true

            StyledText {
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                text: Tr.tr("Notification center")
                font: Tokens.font.title.medium
                wrapMode: Text.WrapAtWordBoundaryOrAnywhere
            }
            StyledText {
                text: root.notifCount
                color: Colours.palette.m3onSurfaceVariant
                font: Tokens.font.label.large
            }
            IconButton {
                objectName: "closeNotificationCenter"
                icon: "close"
                type: IconButton.Text
                padding: Tokens.padding.extraSmall
                onClicked: root.screenState.sidebar = false
                Accessible.name: Tr.tr("Close notification center")
            }
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: Tokens.spacing.small

            IconTextButton {
                objectName: "notificationDoNotDisturb"
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                icon: Notifs.dnd ? "do_not_disturb_on" : "notifications_active"
                text: Tr.tr("Do not disturb")
                type: IconTextButton.Tonal
                isToggle: true
                checked: Notifs.dnd
                onClicked: Notifs.dnd = !Notifs.dnd
            }
            Item { Layout.fillWidth: true }
            TextButton {
                objectName: "clearAllNotifications"
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                text: Tr.tr("Clear all")
                type: TextButton.Text
                disabled: root.notifCount === 0
                onClicked: Notifs.clearAll()
            }
        }

        StyledText {
            Layout.fillWidth: true
            visible: Notifs.lastError !== ""
            text: Notifs.lastError
            textFormat: Text.PlainText
            color: Colours.palette.m3error
            font: Tokens.font.body.small
            wrapMode: Text.WrapAtWordBoundaryOrAnywhere
        }
    }

    ClippingRectangle {
        id: clipRect

        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: header.bottom
        anchors.bottom: parent.bottom
        anchors.topMargin: Tokens.spacing.medium
        radius: Tokens.rounding.medium
        color: "transparent"

        ColumnLayout {
            anchors.centerIn: parent
            width: Math.max(0, parent.width - Tokens.padding.medium * 2)
            visible: root.notifCount === 0
            spacing: Tokens.spacing.medium

            MaterialIcon {
                Layout.alignment: Qt.AlignHCenter
                text: "notifications_none"
                color: Colours.palette.m3outline
                fontStyle: Tokens.font.icon.extraLarge
            }
            StyledText {
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                horizontalAlignment: Text.AlignHCenter
                wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                text: Tr.tr("No notifications")
                color: Colours.palette.m3onSurfaceVariant
                font: Tokens.font.title.medium
            }
            StyledText {
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                horizontalAlignment: Text.AlignHCenter
                wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                text: Tr.tr("New notifications and screenshots appear here.")
                color: Colours.palette.m3outline
                font: Tokens.font.body.small
            }
        }

        StyledFlickable {
            id: view

            objectName: "notificationCenterScroll"
            anchors.fill: parent
            flickableDirection: Flickable.VerticalFlick
            contentWidth: width
            contentHeight: notifList.implicitHeight

            StyledScrollBar.vertical: StyledScrollBar { flickable: view }

            NotifDockList {
                id: notifList
                props: root.props
                screenState: root.screenState
                container: view
            }
        }
    }
}
