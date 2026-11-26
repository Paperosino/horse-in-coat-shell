pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Wayland
import Quickshell.Hyprland
import Hyprstack.Config
import Hyprstack.I18n
import qs.components
import qs.components.controls
import qs.services

// Modal presentation only: cancellation/commit remain owned by LogoutFlow.
PanelWindow {
    id: root

    property var blockers: []
    property bool cancelEnabled: true
    property bool forceEnabled: true
    signal cancelRequested()
    signal forceRequested()

    property string title: Tr.tr("Applications preventing sign out")
    anchors {left:true;right:true;top:true;bottom:true}
    exclusionMode:ExclusionMode.Ignore
    WlrLayershell.namespace:"hics-logout-confirmation"
    WlrLayershell.layer:WlrLayer.Overlay
    WlrLayershell.keyboardFocus:visible?WlrKeyboardFocus.Exclusive:WlrKeyboardFocus.None
    color: Qt.alpha(Colours.palette.m3scrim,0.45)
    contentItem.Config.screen: screen?.name ?? ""
    contentItem.Tokens.screen: screen?.name ?? ""
    onVisibleChanged: if(visible)screen=Quickshell.screens.find(s=>s.name===Hypr.focusedMonitor?.name)??Quickshell.screens[0]
    onBackingWindowVisibleChanged: if (backingWindowVisible) card.forceActiveFocus()
    HyprlandFocusGrab {active:root.visible;windows:[root];onCleared:if(root.cancelEnabled)root.cancelRequested()}
    MouseArea {anchors.fill:parent;acceptedButtons:Qt.AllButtons;onClicked:if(root.cancelEnabled)root.cancelRequested()}
    StyledRect {
        id:card
        anchors.centerIn:parent
        width:Math.min(520*Tokens.scale,parent.width-24*Tokens.scale)
        height:Math.min(440*Tokens.scale,parent.height-24*Tokens.scale)
        radius:Tokens.rounding.extraLarge
        color:Colours.palette.m3surface
        focus:root.visible
        Keys.onEscapePressed:if(root.cancelEnabled)root.cancelRequested()
        MouseArea {anchors.fill:parent;acceptedButtons:Qt.AllButtons}

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
                disabled: !root.cancelEnabled
                type: ButtonBase.Tonal
                text: Tr.tr("Cancel")
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                onClicked: root.cancelRequested()
            }
            TextButton {
                objectName: "logoutForce"
                disabled: !root.forceEnabled
                text: Tr.tr("Force sign out")
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                onClicked: root.forceRequested()
            }
        }
    }
    }
}
