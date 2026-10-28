pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import Quickshell
import Hyprstack.Config
import Hyprstack.I18n
import qs.components
import qs.components.controls
import qs.services

// A non-modal view: the coordinator owns the decision and the blocker model.
FloatingWindow {
    id: root

    property var blockers: []
    signal cancelRequested()
    signal forceRequested()

    title: Tr.tr("Applications preventing sign out")
    implicitWidth: 520
    implicitHeight: 400
    minimumSize.width: 320
    minimumSize.height: 280
    color: Colours.palette.m3surface
    contentItem.Config.screen: screen?.name ?? ""
    contentItem.Tokens.screen: screen?.name ?? ""
    onClosed: cancelRequested()

    ColumnLayout {
        objectName: "logoutDialogContent"
        anchors.fill: parent
        anchors.margins: Tokens.padding.large
        spacing: Tokens.spacing.medium

        StyledText {
            text: Tr.tr("Applications preventing sign out")
            font: Tokens.font.title.large
            wrapMode: Text.Wrap
            Layout.fillWidth: true
            Layout.minimumWidth: 0
        }
        StyledText {
            text: Tr.tr("Return to these applications to save your work or respond to their warnings.")
            wrapMode: Text.Wrap
            Layout.fillWidth: true
            Layout.minimumWidth: 0
        }
        ListView {
            id: list
            objectName: "logoutBlockerList"
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            Layout.fillHeight: true
            Layout.minimumHeight: 0
            clip: true
            spacing: Tokens.spacing.small
            model: root.blockers
            delegate: StyledRect {
                id: row
                required property var modelData
                width: list.width
                implicitHeight: rowContent.implicitHeight + Tokens.padding.medium * 2
                color: Colours.palette.m3surfaceContainer
                radius: Tokens.rounding.medium
                ColumnLayout {
                    id: rowContent
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.top: parent.top
                    anchors.margins: Tokens.padding.medium
                    spacing: Tokens.spacing.small
                    StyledText {
                        objectName: "logoutBlockerName"
                        text: String(row.modelData.name ?? "")
                        font: Tokens.font.title.small
                        wrapMode: Text.WrapAnywhere
                        Layout.fillWidth: true
                        Layout.minimumWidth: 0
                    }
                    StyledText {
                        objectName: "logoutBlockerReason"
                        text: String(row.modelData.reason ?? "")
                        visible: text.length > 0
                        color: Colours.palette.m3onSurfaceVariant
                        wrapMode: Text.WrapAnywhere
                        Layout.fillWidth: true
                        Layout.minimumWidth: 0
                    }
                }
            }
        }
        StyledText {
            text: Tr.tr("Forcing sign out can cause unsaved work to be lost.")
            color: Colours.palette.m3error
            wrapMode: Text.Wrap
            Layout.fillWidth: true
            Layout.minimumWidth: 0
        }
        RowLayout {
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            Layout.alignment: Qt.AlignRight
            TextButton {
                objectName: "logoutCancel"
                type: ButtonBase.Tonal
                text: Tr.tr("Cancel")
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                onClicked: root.cancelRequested()
            }
            TextButton {
                objectName: "logoutForce"
                text: Tr.tr("Force sign out")
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                onClicked: root.forceRequested()
            }
        }
    }
}
