import QtQuick
import Quickshell

QtObject {
    required property ShellScreen screen
    property string currentName
    property bool hasCurrent
    property Item taskButton

    signal detachRequested(mode: string)
}
