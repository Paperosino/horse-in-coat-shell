pragma Singleton
import QtQuick
import Quickshell
import qs.services
Singleton {
    readonly property color mPrimary: Colours.palette.m3primary
    readonly property color mOnPrimary: Colours.palette.m3onPrimary
    readonly property color mSecondary: Colours.palette.m3secondary
    readonly property color mOnSecondary: Colours.palette.m3onSecondary
    readonly property color mTertiary: Colours.palette.m3tertiary
    readonly property color mSurface: Colours.palette.m3surface
    readonly property color mSurfaceVariant: Colours.palette.m3surfaceVariant
    readonly property color mSurfaceContainer: Colours.palette.m3surfaceContainer
    readonly property color mSurfaceContainerHigh: Colours.palette.m3surfaceContainerHigh
    readonly property color mSurfaceContainerLow: Colours.palette.m3surfaceContainerLow
    readonly property color mOnSurface: Colours.palette.m3onSurface
    readonly property color mOnSurfaceVariant: Colours.palette.m3onSurfaceVariant
    readonly property color mOutline: Colours.palette.m3outline
    readonly property color mOutlineVariant: Colours.palette.m3outlineVariant
    readonly property color mError: Colours.palette.m3error
    readonly property color mOnError: Colours.palette.m3onError
    readonly property color mShadow: Colours.palette.m3shadow
    readonly property color mHover: Qt.alpha(mPrimary, 0.12)
}
