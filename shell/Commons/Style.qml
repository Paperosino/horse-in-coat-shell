pragma Singleton
import QtQuick
import Quickshell
import Hyprstack.Config
Singleton {
    readonly property real uiScaleRatio: Tokens.scale
    readonly property real marginXXS: Tokens.spacing.extraSmall
    readonly property real marginXS: Tokens.spacing.small
    readonly property real marginS: Tokens.spacing.medium
    readonly property real marginM: Tokens.padding.medium
    readonly property real marginL: Tokens.padding.large
    readonly property real marginXL: Tokens.padding.extraLarge
    readonly property real radiusS: Tokens.rounding.small
    readonly property real radiusM: Tokens.rounding.medium
    readonly property real radiusL: Tokens.rounding.large
    readonly property real radiusXL: Tokens.rounding.extraLarge
    readonly property int fontSizeXS: 10 * Tokens.scale
    readonly property int fontSizeS: 12 * Tokens.scale
    readonly property int fontSizeM: 14 * Tokens.scale
    readonly property int fontSizeL: 16 * Tokens.scale
    readonly property int fontSizeXL: 20 * Tokens.scale
    readonly property int animationFast: Tokens.anim.durations.small
    readonly property int animationNormal: Tokens.anim.durations.normal
    readonly property int animationSlow: Tokens.anim.durations.large
}
