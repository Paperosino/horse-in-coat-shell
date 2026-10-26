pragma ComponentBehavior: Bound

import QtQuick
import Quickshell
import Quickshell.Wayland
import Hyprstack.Config
import qs.components
import qs.components.containers
import qs.modules.extensions
import qs.services

Variants {
    model: Screens.screens.filter(s => GlobalConfig.forScreen(s.name).background.enabled)

    StyledWindow {
        id: win

        required property ShellScreen modelData

        screen: modelData
        readonly property string outputName: screen?.name ?? ""
        name: "background"
        WlrLayershell.exclusionMode: ExclusionMode.Ignore
        WlrLayershell.layer: contentItem.Config.background.wallpaperEnabled ? WlrLayer.Background : WlrLayer.Bottom
        WlrLayershell.keyboardFocus: !Presentation.privateOn(win.screen) ? WlrKeyboardFocus.OnDemand : WlrKeyboardFocus.None
        color: contentItem.Config.background.wallpaperEnabled && LiveWallpapers.forScreen(outputName).kind !== "engine" ? "black" : "transparent"
        // Static/video wallpapers have an opaque black base over the full output.
        surfaceFormat.opaque: color.a === 1

        anchors.top: true
        anchors.bottom: true
        anchors.left: true
        anchors.right: true

        ShellState.ComponentRef {
            screen: win.screen
            slot: "background"
            component: win
        }

        Item {
            id: behindClock

            anchors.fill: parent

            Loader {
                id: wallpaper

                asynchronous: true

                anchors.fill: parent
                active: !!win.screen && Config.background.wallpaperEnabled && (LiveWallpapers.forScreen(win.outputName).kind === "static" || LiveWallpapers.forScreen(win.outputName).kind === "engine" && !LiveWallpapers.videoSource(LiveWallpapers.forScreen(win.outputName)).toString() && !LiveWallpapers.engineRunning[win.outputName])

                sourceComponent: Wallpaper {}
            }

            LiveWallpaper {
                anchors.fill: parent
                screen: win.screen
                visible: Config.background.wallpaperEnabled
            }

            Visualiser {
                anchors.fill: parent
                screen: win.modelData
                wallpaper: wallpaper
            }
        }

        Loader {
            objectName: "desktopIconGrid"
            anchors.fill:parent
            readonly property var bar: ShellState.componentsFor(win.screen)?.bar
            readonly property real edgeGap: 16 * Tokens.scale
            anchors.topMargin: edgeGap + (bar && !bar.atBottom ? bar.contentWidth : 0) + ExtraPanels.inset(win.outputName,"top") + (DockConf.enabled && DockConf.position === "top" ? (DockConf.iconSize+32)*Tokens.scale : 0)
            anchors.leftMargin:(DockConf.enabled&&DockConf.position==="left"?DockConf.iconSize+40:20)*Tokens.scale
            anchors.rightMargin:(DockConf.enabled&&DockConf.position==="right"?DockConf.iconSize+40:20)*Tokens.scale
            anchors.bottomMargin:edgeGap + (bar?.atBottom ? bar.contentWidth : 0) + ExtraPanels.inset(win.outputName,"bottom") + (DockConf.enabled&&DockConf.position==="bottom" ? (DockConf.iconSize+32)*Tokens.scale : 0)
            active:DesktopIcons.onScreen(win.screen)
            sourceComponent:DesktopFileView {screen:win.screen}
        }

        SettingsContextMenu {
            id: desktopMenu
            actions: [{label:"Desktop settings",icon:"wallpaper",page:"appearance"},
                {label:"Display settings",icon:"monitor",page:"display"},
                {label:"Panel settings",icon:"view_week",page:"statusbar-layout"}]
        }
        TapHandler {
            enabled: !DesktopIcons.onScreen(win.screen) && !Presentation.privateOn(win.screen)
            acceptedButtons: Qt.RightButton
            onTapped: point => desktopMenu.openAt(win.contentItem, point.position.x, point.position.y, false)
        }

        PluginDesktop { anchors.fill: parent; screen: win.screen }

        Loader {
            id: clockLoader

            asynchronous: true
            active: Config.background.desktopClock.enabled

            anchors.margins: Tokens.padding.extraLargeIncreased
            anchors.leftMargin: Tokens.padding.extraLargeIncreased + Tokens.sizes.bar.innerWidth + Math.max(Tokens.padding.small, (Config.border.thickness * Tokens.scale))

            state: Config.background.desktopClock.position
            states: [
                State {
                    name: "top-left"

                    AnchorChanges {
                        target: clockLoader
                        anchors.top: parent.top
                        anchors.left: parent.left
                    }
                },
                State {
                    name: "top-center"

                    AnchorChanges {
                        target: clockLoader
                        anchors.top: parent.top
                        anchors.horizontalCenter: parent.horizontalCenter
                    }
                },
                State {
                    name: "top-right"

                    AnchorChanges {
                        target: clockLoader
                        anchors.top: parent.top
                        anchors.right: parent.right
                    }
                },
                State {
                    name: "middle-left"

                    AnchorChanges {
                        target: clockLoader
                        anchors.verticalCenter: parent.verticalCenter
                        anchors.left: parent.left
                    }
                },
                State {
                    name: "middle-center"

                    AnchorChanges {
                        target: clockLoader
                        anchors.verticalCenter: parent.verticalCenter
                        anchors.horizontalCenter: parent.horizontalCenter
                    }
                },
                State {
                    name: "middle-right"

                    AnchorChanges {
                        target: clockLoader
                        anchors.verticalCenter: parent.verticalCenter
                        anchors.right: parent.right
                    }
                },
                State {
                    name: "bottom-left"

                    AnchorChanges {
                        target: clockLoader
                        anchors.bottom: parent.bottom
                        anchors.left: parent.left
                    }
                },
                State {
                    name: "bottom-center"

                    AnchorChanges {
                        target: clockLoader
                        anchors.bottom: parent.bottom
                        anchors.horizontalCenter: parent.horizontalCenter
                    }
                },
                State {
                    name: "bottom-right"

                    AnchorChanges {
                        target: clockLoader
                        anchors.bottom: parent.bottom
                        anchors.right: parent.right
                    }
                }
            ]

            transitions: Transition {
                AnchorAnim {}
            }

            sourceComponent: DesktopClock {
                wallpaper: behindClock
                absX: clockLoader.x
                absY: clockLoader.y
            }
        }
    }
}
