pragma ComponentBehavior: Bound

import QtQuick
import Quickshell
import Quickshell.Hyprland
import Quickshell.Wayland
import Quickshell.Widgets
import Hyprstack.Config
import qs.components
import qs.services

Item {
    id: root

    required property PopoutState popouts
    readonly property Item task: popouts.taskButton
    readonly property var windows: task?.windows ?? []

    implicitWidth: Math.min((QsWindow.window?.screen.width ?? 1000) - Tokens.padding.large * 2,
        previews.implicitWidth)
    implicitHeight: previews.implicitHeight

    function act(operation: string, window: HyprlandToplevel): void {
        popouts.hasCurrent = false;
        Hypr.windowAction(operation, window);
    }

    Flickable {
        anchors.fill: parent
        contentWidth: previews.implicitWidth
        contentHeight: previews.implicitHeight
        flickableDirection: Flickable.HorizontalFlick
        boundsBehavior: Flickable.StopAtBounds
        clip: true

        Row {
            id: previews
            spacing: Tokens.spacing.medium

            Repeater {
                model: ScriptModel { values: root.windows }

                delegate: Column {
                    id: card

                    required property HyprlandToplevel modelData
                    readonly property bool minimized: Hypr.isMinimized(modelData)
                    width: 250 * Tokens.scale
                    spacing: Tokens.spacing.small

                    StyledClippingRect {
                        width: 250 * Tokens.scale
                        height: 140 * Tokens.scale
                        radius: Tokens.rounding.medium
                        color: Colours.palette.m3surfaceContainerLowest
                        clip: true

                        Loader {
                            anchors.fill: parent
                            active: root.visible && !card.minimized && !!card.modelData?.wayland
                            sourceComponent: ScreencopyView {
                                captureSource: card.modelData?.wayland ?? null
                                live: true
                                constraintSize: Qt.size(250, 140)
                            }
                        }

                        MaterialIcon {
                            anchors.centerIn: parent
                            visible: card.minimized
                            text: "minimize"
                            color: Colours.palette.m3onSurfaceVariant
                        }

                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            onClicked: root.act("activate", card.modelData)
                        }
                    }

                    StyledText {
                        width: parent.width
                        text: card.modelData?.title ?? ""
                        elide: Text.ElideRight
                        font: Tokens.font.body.small
                    }

                    Row {
                        spacing: 4 * Tokens.scale
                        WindowButton {
                            icon: card.minimized ? "open_in_full" : "minimize"
                            onClicked: root.act(card.minimized ? "restore" : "minimize", card.modelData)
                        }
                        WindowButton {
                            icon: Hypr.isMaximized(card.modelData) ? "filter_none" : "crop_square"
                            onClicked: root.act("maximize", card.modelData)
                        }
                        WindowButton {
                            icon: "close"
                            danger: true
                            onClicked: root.act("close", card.modelData)
                        }
                    }
                }
            }
        }
    }

    component WindowButton: Rectangle {
        required property string icon
        property bool danger
        signal clicked
        width: 38 * Tokens.scale
        height: 30 * Tokens.scale
        radius: Tokens.rounding.small
        color: mouse.containsMouse ? Colours.palette.m3surfaceContainerHighest : "transparent"
        Behavior on color { CAnim {} }

        MaterialIcon {
            anchors.centerIn: parent
            text: parent.icon
            color: parent.danger ? Colours.palette.m3error : Colours.palette.m3onSurface
        }

        MouseArea {
            id: mouse
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: parent.clicked()
        }
    }
}
