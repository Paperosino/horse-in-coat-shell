pragma ComponentBehavior: Bound

import QtQuick
import Quickshell
import Hyprstack
import Hyprstack.Config
import qs.components

Item {
    id: root

    required property ScreenState screenState
    property bool atBottom: false

    readonly property bool shouldBeActive: screenState.clipboard
    property real offsetScale: shouldBeActive ? 0 : 1

    function dismissOutside(item: Item, x: real, y: real): void {
        if (!screenState.clipboard) return;
        const point = mapFromItem(item, x, y);
        if (!contains(point)) screenState.clipboard = false;
    }

    implicitWidth: content.implicitWidth
    implicitHeight: content.implicitHeight

    visible: offsetScale < 1
    opacity: 1 - offsetScale
    y: atBottom
        ? (parent?.height ?? 0) - height + (implicitHeight + 5) * offsetScale
        : (-implicitHeight - 5) * offsetScale

    Behavior on offsetScale {
        Anim {}
    }

    ClipboardContent {
        id: content
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.top: parent.top
        screenState: root.screenState
    }
}
