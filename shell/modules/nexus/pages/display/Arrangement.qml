pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import Hyprstack.Config
import qs.components
import qs.services

// Interactive monitor arrangement canvas. Monitors are laid out by their
// logical position and size; the view auto-fits all of them. Dragging a
// monitor stages its position (the transform freezes for the duration so
// the rectangle tracks the cursor 1:1); on release it snaps its edges to
// neighbours, to their centres and to the layout origin. Tapping selects.
StyledRect {
    id: root

    property var monitors: []
    property var staged: ({})
    property string selected: ""

    readonly property real pad: Tokens.padding.large

    property rect contentBounds: Qt.rect(0, 0, 16, 9)
    readonly property rect activeBounds: dragFrozen ? frozenBounds : contentBounds
    property real k: 1
    property real offX: 0
    property real offY: 0
    property bool dragFrozen: false
    property rect frozenBounds: Qt.rect(0, 0, 16, 9)

    signal select(name: string)
    signal moved(name: string, x: int, y: int)

    function effectiveX(m: var): real {
        return root.staged[m.name]?.x ?? m.x;
    }

    function effectiveY(m: var): real {
        return root.staged[m.name]?.y ?? m.y;
    }

    function computeBounds(): rect {
        const list = root.monitors;
        if (!list.length)
            return Qt.rect(0, 0, 16, 9);
        let minX = effectiveX(list[0]);
        let minY = effectiveY(list[0]);
        let maxX = minX + list[0].logicalWidth;
        let maxY = minY + list[0].logicalHeight;
        for (let i = 1; i < list.length; i++) {
            const m = list[i];
            const x = effectiveX(m);
            const y = effectiveY(m);
            minX = Math.min(minX, x);
            minY = Math.min(minY, y);
            maxX = Math.max(maxX, x + m.logicalWidth);
            maxY = Math.max(maxY, y + m.logicalHeight);
        }
        return Qt.rect(minX, minY, Math.max(1, maxX - minX), Math.max(1, maxY - minY));
    }

    // Fit the active bounds into the canvas, preserving aspect. Ignores
    // premature geometry (the page incubates before the layout assigns its
    // final size) — a later change will trigger a proper refit.
    function refit(): void {
        if (width < 100 || height < 100)
            return;
        const b = root.activeBounds;
        const availW = Math.max(60, width - pad * 2);
        const availH = Math.max(60, height - pad * 2);
        const s = Math.min(availW / b.width, availH / b.height);
        root.k = s;
        root.offX = (width - b.width * s) / 2;
        root.offY = (height - b.height * s) / 2;
    }

    function updateBounds(): void {
        root.contentBounds = computeBounds();
        if (!root.dragFrozen)
            refit();
    }

    onWidthChanged: refit()
    onHeightChanged: refit()
    onMonitorsChanged: updateBounds()
    onStagedChanged: updateBounds()

    Layout.fillWidth: true
    Layout.preferredHeight: 300 * Tokens.scale
    Layout.minimumHeight: 200 * Tokens.scale
    Layout.maximumHeight: 400 * Tokens.scale
    color: Colours.tPalette.m3surfaceContainer
    radius: Tokens.rounding.extraLarge
    clip: true

    // The layout settles asynchronously after page incubation; make sure the
    // transform is recomputed once more with the final geometry.
    Timer {
        interval: 400
        running: true
        repeat: false
        onTriggered: root.refit()
    }

    // Snap the dragged monitor's edges to neighbours' corresponding edges,
    // to neighbour centres and to the layout origin; the smallest adjustment
    // within the threshold wins, which makes a monitor "jump" to the far side
    // of a neighbour as its own edge crosses over.
    function snap(name: string, nx: real, ny: real): var {
        const thresh = 64;
        const self = monitors.find(m => m.name === name);
        const result = {
            x: Math.round(nx),
            y: Math.round(ny)
        };
        if (!self)
            return result;
        const candX = [0, -self.logicalWidth];
        const candY = [0, -self.logicalHeight];
        for (const o of monitors) {
            if (o.name === name)
                continue;
            const ox = effectiveX(o);
            const oy = effectiveY(o);
            candX.push(ox, ox - self.logicalWidth, ox + o.logicalWidth, ox + o.logicalWidth - self.logicalWidth, ox + (o.logicalWidth - self.logicalWidth) / 2);
            candY.push(oy, oy - self.logicalHeight, oy + o.logicalHeight, oy + o.logicalHeight - self.logicalHeight, oy + (o.logicalHeight - self.logicalHeight) / 2);
        }
        let bestX = null;
        for (const c of candX) {
            const d = c - nx;
            if (Math.abs(d) <= thresh && (bestX === null || Math.abs(d) < Math.abs(bestX)))
                bestX = d;
        }
        let bestY = null;
        for (const c of candY) {
            const d = c - ny;
            if (Math.abs(d) <= thresh && (bestY === null || Math.abs(d) < Math.abs(bestY)))
                bestY = d;
        }
        if (bestX !== null)
            result.x = Math.round(nx + bestX);
        if (bestY !== null)
            result.y = Math.round(ny + bestY);
        return result;
    }

    Repeater {
        model: root.monitors

        MonitorRect {
            canvas: root
        }
    }
}
