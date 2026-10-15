pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Widgets
import Hyprstack.Config
import qs.components
import qs.components.controls
import qs.components.containers
import qs.components.effects
import qs.services

Item {
    id: root

    required property NotifData notif

    Layout.fillWidth: true
    implicitHeight: notif?.screenshot ? imageActions.implicitHeight : flickable.contentHeight

    layer.enabled: !notif?.screenshot
    layer.smooth: true
    layer.effect: Mask {
        maskSource: gradientMask
    }

    Flow {
        id: imageActions

        width: root.width
        visible: root.notif?.screenshot ?? false
        spacing: Tokens.spacing.small

        Repeater {
            model: root.notif?.screenshot ? root.notif.actions : []

            IconTextButton {
                required property var modelData

                objectName: "notificationAction_" + modelData.identifier + "_" + (root.notif?.historyId ?? "")
                text: modelData.text
                icon: ({open: "open_in_new", copy: "content_copy", save: "save", reveal: "folder_open"})[modelData.identifier]
                type: IconTextButton.Tonal
                font: Tokens.font.body.small
                onClicked: modelData.invoke()
            }
        }
    }

    Item {
        id: gradientMask

        anchors.fill: parent
        layer.enabled: true
        visible: false

        Rectangle {
            anchors.fill: parent

            gradient: Gradient {
                orientation: Gradient.Horizontal

                GradientStop {
                    position: 0
                    color: Qt.rgba(0, 0, 0, 0)
                }
                GradientStop {
                    position: 0.1
                    color: Qt.rgba(0, 0, 0, 1)
                }
                GradientStop {
                    position: 0.9
                    color: Qt.rgba(0, 0, 0, 1)
                }
                GradientStop {
                    position: 1
                    color: Qt.rgba(0, 0, 0, 0)
                }
            }
        }

        Rectangle {
            anchors.top: parent.top
            anchors.bottom: parent.bottom
            anchors.left: parent.left

            implicitWidth: parent.width / 2
            opacity: flickable.contentX > 0 ? 0 : 1

            Behavior on opacity {
                Anim {
                    type: Anim.DefaultEffects
                }
            }
        }

        Rectangle {
            anchors.top: parent.top
            anchors.bottom: parent.bottom
            anchors.right: parent.right

            implicitWidth: parent.width / 2
            opacity: flickable.contentX < flickable.contentWidth - parent.width ? 0 : 1

            Behavior on opacity {
                Anim {
                    type: Anim.DefaultEffects
                }
            }
        }
    }

    StyledFlickable {
        id: flickable

        anchors.fill: parent
        visible: !root.notif?.screenshot
        contentWidth: Math.max(width, actionList.implicitWidth)
        contentHeight: actionList.implicitHeight

        RowLayout {
            id: actionList

            anchors.fill: parent
            spacing: Tokens.spacing.small

            Repeater {
                model: root.notif?.screenshot ? [] : [
                    {
                        isClose: true
                    },
                    ...(root.notif?.actions ?? []),
                    ...(root.notif?.screenshot ? [] : [{isCopy: true}])
                ]

                StyledRect {
                    id: action

                    required property var modelData

                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    implicitWidth: actionInner.implicitWidth + Tokens.padding.medium * 2
                    implicitHeight: actionInner.implicitHeight + Tokens.padding.small

                    Layout.preferredWidth: implicitWidth + (actionStateLayer.pressed ? Tokens.padding.large : 0)
                    radius: actionStateLayer.pressed ? Tokens.rounding.medium / 2 : Tokens.rounding.medium
                    color: Colours.layer(Colours.palette.m3surfaceContainerHighest, 4)

                    Timer {
                        id: copyTimer

                        interval: 3000
                        onTriggered: actionInner.item.text = "content_copy"
                    }

                    StateLayer {
                        id: actionStateLayer

                        onClicked: {
                            if (action.modelData.isClose) {
                                root.notif.close();
                            } else if (action.modelData.isCopy) {
                                Quickshell.clipboardText = root.notif.body;
                                actionInner.item.text = "inventory";
                                copyTimer.start();
                            } else if (action.modelData.invoke) {
                                action.modelData.invoke();
                            }
                        }
                    }

                    Loader {
                        id: actionInner

                        anchors.centerIn: parent
                        sourceComponent: action.modelData.isClose || action.modelData.isCopy ? iconBtn : root.notif?.hasActionIcons ? iconComp : textComp
                    }

                    Component {
                        id: iconBtn

                        MaterialIcon {
                            animate: action.modelData.isCopy ?? false
                            text: action.modelData.isCopy ? "content_copy" : "close"
                            color: Colours.palette.m3onSurfaceVariant
                        }
                    }

                    Component {
                        id: iconComp

                        IconImage {
                            asynchronous: true
                            source: Quickshell.iconPath(action.modelData.identifier)
                        }
                    }

                    Component {
                        id: textComp

                        StyledText {
                            text: action.modelData.text
                            color: Colours.palette.m3onSurfaceVariant
                        }
                    }

                    Behavior on Layout.preferredWidth {
                        Anim {
                            type: Anim.FastSpatial
                        }
                    }

                    Behavior on radius {
                        Anim {
                            type: Anim.FastSpatial
                        }
                    }
                }
            }
        }
    }
}
