import Hyprstack.Config
import QtQuick
import qs.components
import qs.services

StyledRect {
    property bool first
    property bool last

    border.width: GlobalConfig.appearance.highContrast ? 1 * Tokens.scale : 0
    border.color: Colours.palette.m3outlineVariant
    color: Colours.tPalette.m3surfaceContainer
    topLeftRadius: first ? Tokens.rounding.extraLarge : Tokens.rounding.extraSmall
    topRightRadius: first ? Tokens.rounding.extraLarge : Tokens.rounding.extraSmall
    bottomLeftRadius: last ? Tokens.rounding.extraLarge : Tokens.rounding.extraSmall
    bottomRightRadius: last ? Tokens.rounding.extraLarge : Tokens.rounding.extraSmall
}
