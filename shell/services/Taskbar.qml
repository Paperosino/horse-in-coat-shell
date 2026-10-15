pragma Singleton

import QtQuick
import Quickshell
import Quickshell.Io
import qs.utils

Singleton {
    id: root

    property var pinned: []
    property var order: []
    property bool loaded: false

    function persist(): void {
        if (loaded)
            storage.setText(JSON.stringify({ pinned: pinned, order: order }));
    }

    function togglePin(id: string): void {
        if (!id || !loaded) return;
        pinned = pinned.includes(id) ? pinned.filter(key => key !== id) : [...pinned, id];
        if (!order.includes(id)) order = [...order, id];
        persist();
    }

    function move(id: string, target: string, after: bool, visibleIds: var): void {
        if (!loaded || id === target || !visibleIds.includes(id) || !visibleIds.includes(target)) return;
        const next = [...order];
        for (const key of visibleIds)
            if (!next.includes(key)) next.push(key);
        next.splice(next.indexOf(id), 1);
        next.splice(next.indexOf(target) + (after ? 1 : 0), 0, id);
        order = next;
        persist();
    }

    FileView {
        id: storage
        path: `${Paths.config}/taskbar.json`
        printErrors: false
        watchChanges: true
        onFileChanged: reload()
        onLoaded: {
            try {
                const data = JSON.parse(text());
                root.pinned = [...new Set((data.pinned ?? []).filter(id => typeof id === "string"))];
                root.order = [...new Set((data.order ?? []).filter(id => typeof id === "string"))];
            } catch (error) {
                console.warn(`Unable to load taskbar preferences: ${error}`);
            }
            root.loaded = true;
        }
        onLoadFailed: root.loaded = true
    }
}
