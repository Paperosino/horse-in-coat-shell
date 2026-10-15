import QtQuick
import QtQuick.Effects
import Hyprstack.Config
import qs.components
import qs.services

Item {
    id: root

    property int level
    property real dp: [0, 1, 3, 6, 8, 12][level]
    property alias radius: shadow.radius
    property real topLeftRadius: -1
    property real topRightRadius: -1
    property real bottomLeftRadius: -1
    property real bottomRightRadius: -1
    property alias color: shadow.color
    property alias blur: shadow.blur
    property alias spread: shadow.spread
    property alias offset: shadow.offset

    // Menus also use this item as their content container. Hide only the
    // shadow renderer so disabling effects keeps their controls interactive.
    RectangularShadow {
        id: shadow
        anchors.fill: parent
        z: -1
        visible: Effects.uiShadowsEnabled
        color: Qt.alpha(Colours.palette.m3shadow, Effects.shadowOpacity)
        blur: (root.dp * 5) ** 0.7 * Effects.shadowSize / 18 * root.Tokens.scale
        spread: (-root.dp * 0.3 + (root.dp * 0.1) ** 2) * root.Tokens.scale
        offset.y: root.dp / 2 * root.Tokens.scale
    }

    // Per-corner shadow radii arrived in Qt 6.11. Earlier supported versions
    // retain the uniform radius, without an unavailable-property load failure.
    Binding { target: "topLeftRadius" in shadow ? shadow : null; property: "topLeftRadius"; value: root.topLeftRadius }
    Binding { target: "topRightRadius" in shadow ? shadow : null; property: "topRightRadius"; value: root.topRightRadius }
    Binding { target: "bottomLeftRadius" in shadow ? shadow : null; property: "bottomLeftRadius"; value: root.bottomLeftRadius }
    Binding { target: "bottomRightRadius" in shadow ? shadow : null; property: "bottomRightRadius"; value: root.bottomRightRadius }

    Behavior on dp {
        Anim {
            type: Anim.SlowEffects
        }
    }
}
