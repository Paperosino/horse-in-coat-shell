import QtQuick
import Hyprstack.Config
import qs.components
import qs.components.effects
import qs.services

// One monitor on the arrangement canvas. Instantiated by the Repeater in
// Arrangement.qml; `canvas` is the Arrangement. `modelData` is the monitor
// entry, injected by the Repeater through the required property.
Item {
    id: rect

    required property var modelData
    property var canvas: null

    readonly property var mon: modelData
    readonly property real logicalX: canvas ? canvas.effectiveX(modelData) : 0
    readonly property real logicalY: canvas ? canvas.effectiveY(modelData) : 0
    readonly property bool isSelected: canvas ? canvas.selected === modelData.name : false

    readonly property real rawW: (modelData?.logicalWidth ?? 100) * canvas.k
    readonly property real rawH: (modelData?.logicalHeight ?? 60) * canvas.k
    // Uniform upscaling into the minimum box keeps the monitor's aspect
    // ratio at small canvas scales; capped so tiny monitors stay small.
    readonly property real minBoost: Math.min(Math.max(72 * Tokens.scale / rect.rawW, 48 * Tokens.scale / rect.rawH, 1), 4)
    readonly property real dispW: rect.rawW * rect.minBoost
    readonly property real dispH: rect.rawH * rect.minBoost

    x: canvas.offX + (rect.logicalX - canvas.activeBounds.x) * canvas.k + (rect.rawW - rect.dispW) / 2
    y: canvas.offY + (rect.logicalY - canvas.activeBounds.y) * canvas.k + (rect.rawH - rect.dispH) / 2
    width: rect.dispW
    height: rect.dispH
    z: dragArea.pressed ? 1 : 0

    // Animate layout changes (refit, snapping) but track the cursor
    // exactly while dragging.
    Behavior on x {
        enabled: !dragArea.pressed

        Anim {}
    }
    Behavior on y {
        enabled: !dragArea.pressed

        Anim {}
    }

    Elevation {
        anchors.fill: parent

        radius: bg.radius
        level: 3
        opacity: dragArea.pressed ? 1 : 0

        Behavior on opacity {
            Anim {
                type: Anim.DefaultEffects
            }
        }
    }

    StyledRect {
        id: bg

        anchors.fill: parent

        color: rect.isSelected ? Colours.palette.m3primaryContainer : Colours.palette.m3surfaceContainerHigh
        radius: Tokens.rounding.large
        border.width: 2 * Tokens.scale
        border.color: rect.isSelected ? Colours.palette.m3primary : Colours.palette.m3outline
    }

    Column {
        anchors.centerIn: parent
        spacing: 0

        StyledText {
            anchors.horizontalCenter: parent.horizontalCenter
            width: Math.min(implicitWidth, rect.dispW - Tokens.padding.small * 2)
            text: rect.mon?.name ?? ""
            horizontalAlignment: Text.AlignHCenter
            elide: Text.ElideMiddle
            color: rect.isSelected ? Colours.palette.m3onPrimaryContainer : Colours.palette.m3onSurface
            font: Tokens.font.label.small
        }

        StyledText {
            anchors.horizontalCenter: parent.horizontalCenter
            visible: rect.dispH >= 64 * Tokens.scale
            width: Math.min(implicitWidth, rect.dispW - Tokens.padding.small * 2)
            text: rect.mon?.resolution ?? ""
            horizontalAlignment: Text.AlignHCenter
            elide: Text.ElideMiddle
            color: rect.isSelected ? Colours.palette.m3onPrimaryContainer : Colours.palette.m3onSurfaceVariant
            font: Tokens.font.label.small
        }
    }

    MouseArea {
        id: dragArea

        anchors.fill: parent
        preventStealing: true
        cursorShape: pressed ? Qt.ClosedHandCursor : Qt.OpenHandCursor

        property real grabDX: 0
        property real grabDY: 0
        property point lastPos: Qt.point(0, 0)
        property real movedDist: 0

        onPressed: e => {
            if (!rect.canvas)
                return;
            rect.canvas.frozenBounds = rect.canvas.contentBounds;
            rect.canvas.dragFrozen = true;
            const p = dragArea.mapToItem(rect.canvas, e.x, e.y);
            grabDX = (p.x - rect.canvas.offX) / rect.canvas.k + rect.canvas.activeBounds.x - rect.logicalX;
            grabDY = (p.y - rect.canvas.offY) / rect.canvas.k + rect.canvas.activeBounds.y - rect.logicalY;
            lastPos = Qt.point(e.x, e.y);
            movedDist = 0;
        }

        onPositionChanged: e => {
            if (!dragArea.pressed || !rect.canvas)
                return;
            movedDist += Math.hypot(e.x - lastPos.x, e.y - lastPos.y);
            lastPos = Qt.point(e.x, e.y);
            const p = dragArea.mapToItem(rect.canvas, e.x, e.y);
            Monitors.stagePosition(rect.mon.name, (p.x - rect.canvas.offX) / rect.canvas.k + rect.canvas.activeBounds.x - grabDX, (p.y - rect.canvas.offY) / rect.canvas.k + rect.canvas.activeBounds.y - grabDY);
        }

        onReleased: {
            if (!rect.canvas) {
                return;
            }
            if (movedDist < 6 * Tokens.scale) {
                rect.canvas.dragFrozen = false;
                rect.canvas.select(rect.mon.name);
            } else {
                const snapped = rect.canvas.snap(rect.mon.name, rect.logicalX, rect.logicalY);
                rect.canvas.dragFrozen = false;
                rect.canvas.moved(rect.mon.name, snapped.x, snapped.y);
            }
        }
    }
}
