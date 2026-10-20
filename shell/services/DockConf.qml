pragma Singleton

import QtQuick
import Quickshell
import Quickshell.Io
import qs.utils

Singleton {
    id: root

    property bool enabled: false
    property string position: "bottom"
    property int iconSize: 44
    property string menuButtonPosition: "end"
    function setMenuButtonPosition(value: string): void {
        menuButtonPosition = value === "start" ? "start" : "end";
        persist();
    }
    readonly property bool atBottom: position === "bottom"
    readonly property bool vertical: position === "left" || position === "right"
    property bool loaded: false

    function setEnabled(value: bool): void {
        enabled = value;
        persist();
    }

    function setPosition(value: string): void {
        position = sanitizePosition(value);
        persist();
    }

    function setIconSize(value: int): void {
        iconSize = clampIconSize(value);
        persist();
    }

    function sanitizePosition(value: string): string {
        return ["top", "bottom", "left", "right"].includes(value) ? value : "bottom";
    }

    function clampIconSize(value: int): int {
        return Math.max(32, Math.min(64, Math.round(value ?? 44)));
    }

    function persist(): void {
        if (loaded)
            storage.setText(JSON.stringify({ enabled: enabled, position: position, iconSize: iconSize, menuButtonPosition: menuButtonPosition }));
    }

    FileView {
        id: storage

        path: `${Paths.config}/dock.json`
        printErrors: false
        watchChanges: true
        onFileChanged: reload()
        onLoaded: {
            try {
                const data = JSON.parse(text());
                root.enabled = data.enabled === true;
                root.position = root.sanitizePosition(data.position);
                root.menuButtonPosition = data.menuButtonPosition === "start" ? "start" : "end";
                root.iconSize = root.clampIconSize(data.iconSize);
            } catch (error) {
                console.warn(`Unable to load dock preferences: ${error}`);
            }
            root.loaded = true;
        }
        onLoadFailed: root.loaded = true
    }
}
