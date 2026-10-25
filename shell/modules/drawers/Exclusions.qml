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

    function dockDepth(edge: string): real {
        return DockConf.enabled && !bar.fullscreen && !bar.disabled && DockConf.position === edge
            ? DockConf.iconSize * root.bar.Tokens.scale + root.bar.Tokens.padding.small * 2 : 0;
    }

    ExclusionZone {
        anchors.left: true
        exclusiveZone: root.frameThickness + root.dockDepth("left")
    }

    ExclusionZone {
        anchors.top: true
        exclusiveZone: (root.bar.atBottom ? root.frameThickness : root.bar.exclusiveZone) + root.dockDepth("top")
    }

    ExclusionZone {
        anchors.right: true
        exclusiveZone: root.frameThickness + root.dockDepth("right")
    }

    ExclusionZone {
        anchors.bottom: true
        exclusiveZone: (root.bar.atBottom ? root.bar.exclusiveZone : root.frameThickness) + root.dockDepth("bottom")
    }

    component ExclusionZone: StyledWindow {
        visible: !GameMode.quietOn(root.screen)
        screen: root.screen
        name: "border-exclusion"
        exclusiveZone: root.frameThickness
        mask: Region {}
        implicitWidth: 1
        implicitHeight: 1
    }
}
