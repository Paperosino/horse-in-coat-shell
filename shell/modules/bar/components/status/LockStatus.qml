import QtQuick
import QtQuick.Layouts
import qs.components
import qs.services

RowLayout {
    id: root

    required property color colour
    required property int parentSpacing

    property real gap: Hypr.capsLock && Hypr.numLock ? parentSpacing : 0
    property real capsHeight: Hypr.capsLock ? capslockIcon.implicitWidth : 0
    property real numHeight: Hypr.numLock ? numlockIcon.implicitWidth : 0

    spacing: Math.round(gap)

    Behavior on gap {
        Anim {
            type: Anim.SlowEffects
        }
    }

    Behavior on capsHeight {
        Anim {
            type: Anim.SlowEffects
        }
    }

    Behavior on numHeight {
        Anim {
            type: Anim.SlowEffects
        }
    }

    Item {
        implicitWidth: Math.round(root.capsHeight)
        implicitHeight: capslockIcon.implicitHeight

        MaterialIcon {
            id: capslockIcon

            anchors.centerIn: parent

            scale: Hypr.capsLock ? 1 : 0.5
            opacity: Hypr.capsLock ? 1 : 0

            text: "keyboard_capslock_badge"
            color: root.colour
            fill: 1
            grade: 25

            Behavior on opacity {
                Anim {
                    type: Anim.DefaultEffects
                }
            }

            Behavior on scale {
                Anim {}
            }
        }
    }

    Item {
        implicitWidth: Math.round(root.numHeight)
        implicitHeight: numlockIcon.implicitHeight

        MaterialIcon {
            id: numlockIcon

            anchors.centerIn: parent

            scale: Hypr.numLock ? 1 : 0.5
            opacity: Hypr.numLock ? 1 : 0

            text: "looks_one"
            color: root.colour
            fill: 1
            grade: 25

            Behavior on opacity {
                Anim {
                    type: Anim.DefaultEffects
                }
            }

            Behavior on scale {
                Anim {}
            }
        }
    }
}
