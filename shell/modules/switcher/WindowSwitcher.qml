pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Wayland
import Quickshell.Widgets
import Hyprstack.Config
import Hyprstack.I18n
import qs.components
import qs.components.containers
import qs.components.misc
import qs.services
import qs.utils

Scope {
    CustomShortcut { name: "switcherNext"; description: "Next window"; onPressed: WindowSwitcher.step(1) }
    CustomShortcut { name: "switcherPrev"; description: "Previous window"; onPressed: WindowSwitcher.step(-1) }
    CustomShortcut {
        name: "switcherAccept"
        description: "Activate selected window"
        onPressed: WindowSwitcher.accept()
        // The compositor's global dispatcher retains the originating key's
        // state: releasing Alt emits released, whereas Enter emits pressed.
        onReleased: WindowSwitcher.accept()
    }
    CustomShortcut { name: "switcherCancel"; description: "Cancel window switching"; onPressed: WindowSwitcher.close() }

    StyledWindow {
        id: popup
        name: "window-switcher"
        screen: WindowSwitcher.screen ?? Screens.screens[0]
        visible: WindowSwitcher.opened && Hypr.stacking
        WlrLayershell.layer: WlrLayer.Overlay
        WlrLayershell.exclusionMode: ExclusionMode.Ignore
        WlrLayershell.keyboardFocus: WlrKeyboardFocus.None

        readonly property int columns: Math.max(1, Math.min(4, WindowSwitcher.windows.length,
            Math.floor((screen.width - 80 * Tokens.scale) / (232 * Tokens.scale))))
        implicitWidth: grid.columns * (220 * Tokens.scale) + (grid.columns - 1) * grid.columnSpacing + 40 * Tokens.scale
        implicitHeight: Math.min(screen.height * .75, grid.implicitHeight + 70 * Tokens.scale)

        StyledRect {
            anchors.fill: parent
            color: Colours.palette.m3surfaceContainer
            radius: Tokens.rounding.large
            border.width: 1
            border.color: Colours.palette.m3outlineVariant

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 20 * Tokens.scale
                spacing: 12 * Tokens.scale

                StyledText {
                    Layout.fillWidth: true
                    text: Tr.tr("Switch windows")
                    font: Tokens.font.title.medium
                }

                Flickable {
                    id: scroller
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    implicitHeight: grid.implicitHeight
                    clip: true
                    contentWidth: width
                    contentHeight: grid.implicitHeight
                    boundsBehavior: Flickable.StopAtBounds

                    GridLayout {
                        id: grid
                        columns: popup.columns
                        columnSpacing: 12 * Tokens.scale
                        rowSpacing: 12 * Tokens.scale

                        Repeater {
                            model: WindowSwitcher.windows
                            delegate: StyledRect {
                                id: card
                                required property var modelData
                                required property int index
                                readonly property bool selected: index === WindowSwitcher.index
                                readonly property bool minimized: Hypr.isMinimized(modelData)
                                implicitWidth: 220 * Tokens.scale
                                implicitHeight: 166 * Tokens.scale
                                radius: Tokens.rounding.medium
                                color: selected ? Colours.palette.m3secondaryContainer : Colours.palette.m3surfaceContainerHigh
                                border.width: selected ? 3 : 1
                                border.color: selected ? Colours.palette.m3primary : Colours.palette.m3outlineVariant

                                Column {
                                    anchors.fill: parent
                                    anchors.margins: 10 * Tokens.scale
                                    spacing: 8 * Tokens.scale

                                    RowLayout {
                                        width: parent.width
                                        spacing: 8 * Tokens.scale
                                        IconImage {
                                            implicitSize: 20 * Tokens.scale
                                            source: Icons.getAppIcon(card.modelData?.lastIpcObject.class ?? "", "application-x-executable")
                                        }
                                        StyledText {
                                            Layout.fillWidth: true
                                            text: card.modelData?.title ?? ""
                                            elide: Text.ElideRight
                                            font: Tokens.font.body.small
                                        }
                                    }

                                    StyledClippingRect {
                                        width: parent.width
                                        height: 112 * Tokens.scale
                                        radius: Tokens.rounding.small
                                        color: Colours.palette.m3surfaceContainerLowest
                                        Loader {
                                            anchors.fill: parent
                                            active: popup.visible && !card.minimized && !!card.modelData?.wayland
                                            sourceComponent: ScreencopyView {
                                                captureSource: card.modelData?.wayland ?? null
                                                live: false
                                                constraintSize: Qt.size(400, 230)
                                            }
                                        }
                                        Column {
                                            anchors.centerIn: parent
                                            visible: card.minimized
                                            spacing: 8 * Tokens.scale
                                            MaterialIcon { anchors.horizontalCenter: parent.horizontalCenter; text: "minimize" }
                                            StyledText { text: Tr.tr("Minimized") }
                                        }
                                    }
                                }
                                MouseArea {
                                    anchors.fill: parent
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: { WindowSwitcher.index = card.index; WindowSwitcher.accept(); }
                                }
                                onSelectedChanged: if (selected) Qt.callLater(() => {
                                    if (y < scroller.contentY) scroller.contentY = y;
                                    else if (y + height > scroller.contentY + scroller.height)
                                        scroller.contentY = y + height - scroller.height;
                                })
                            }
                        }
                    }
                }
            }
        }
    }
}
