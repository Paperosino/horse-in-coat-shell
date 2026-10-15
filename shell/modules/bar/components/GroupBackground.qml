import QtQuick
import Hyprstack.Config
import qs.components
import qs.services

StyledRect {
    readonly property real verticalInset: Hypr.stacking ? 2 * Tokens.scale : 0

    anchors.left: parent.left
    anchors.right: parent.right
    anchors.verticalCenter: parent.verticalCenter
    height: Math.max(0, (parent?.height ?? 0) - verticalInset * 2)
    z: -1

    color: Colours.tPalette.m3surfaceContainer
    radius: Tokens.rounding.full
}
