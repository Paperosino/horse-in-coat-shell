pragma ComponentBehavior: Bound

import QtQuick
import Quickshell
import Hyprstack.Config
import qs.components.containers
import qs.modules.bar as Bar
import qs.services

Scope {
    id: root

    required property ShellScreen screen
    required property Bar.BarWrapper bar
    readonly property real frameThickness: Hypr.stacking || !Tiling.desktopFrame ? 0 : (root.bar.Config.border.thickness * root.bar.Tokens.scale)

    ExclusionZone {
        anchors.left: true
    }

    ExclusionZone {
        anchors.top: true
        exclusiveZone: root.bar.atBottom ? root.frameThickness : root.bar.exclusiveZone
    }

    ExclusionZone {
        anchors.right: true
    }

    ExclusionZone {
        anchors.bottom: true
        exclusiveZone: root.bar.atBottom ? root.bar.exclusiveZone : root.frameThickness
    }

    component ExclusionZone: StyledWindow {
        screen: root.screen
        name: "border-exclusion"
        exclusiveZone: root.frameThickness
        mask: Region {}
        implicitWidth: 1
        implicitHeight: 1
    }
}
