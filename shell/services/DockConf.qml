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
    property bool notificationBadges: true
    property string badgeSource: "both"
    property bool animations: true
    property bool windowAnimations: true
    property real lift: 28
    property real magnification: 1.35
    property real spread: 64
    property real damping: 0.8
    property int animationDuration: 420
    property bool loaded: false
    function resetMotion(): void {
        animations = windowAnimations = true;
        lift=28;magnification=1.35;spread=64;damping=0.8;animationDuration=420;
        persist();
    }
    function setMotion(option: string, value: var): void {
        if (option === "animations") animations = !!value;
        else if (option === "windowAnimations") windowAnimations = !!value;
        else if (option === "lift") lift = Math.max(8, Math.min(40, Number(value)));
        else if (option === "magnification") magnification = Math.max(1, Math.min(1.5, Number(value)));
        else if (option === "spread") spread = Math.max(36, Math.min(120, Number(value)));
        else if (option === "damping") damping = Math.max(0.55, Math.min(1, Number(value)));
        else if (option === "animationDuration") animationDuration = Math.max(240, Math.min(700, Number(value)));
        persist();
    }

    function setBadges(enabled: bool, source: string): void {
        notificationBadges = enabled;
        badgeSource = ["both", "applications", "notifications"].includes(source) ? source : "both";
        persist();
    }

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
            storage.setText(JSON.stringify({ notificationBadges: notificationBadges, badgeSource: badgeSource, enabled: enabled, position: position, iconSize: iconSize, menuButtonPosition: menuButtonPosition, animations: animations, windowAnimations: windowAnimations, lift: lift, magnification: magnification, spread: spread, damping: damping, animationDuration: animationDuration }));
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
                root.notificationBadges = data.notificationBadges !== false;
                root.badgeSource = ["both", "applications", "notifications"].includes(data.badgeSource) ? data.badgeSource : "both";
                root.enabled = data.enabled === true;
                root.position = root.sanitizePosition(data.position);
                root.menuButtonPosition = data.menuButtonPosition === "start" ? "start" : "end";
                root.iconSize = root.clampIconSize(data.iconSize);
                root.animations = data.animations !== false;
                root.windowAnimations = data.windowAnimations !== false;
                root.lift = Math.max(8, Math.min(40, Number(data.lift ?? 28)));
                root.magnification = Math.max(1, Math.min(1.5, Number(data.magnification ?? 1.35)));
                root.spread = Math.max(36, Math.min(120, Number(data.spread ?? 64)));
                root.damping = Math.max(0.55, Math.min(1, Number(data.damping ?? 0.8)));
                root.animationDuration = Math.max(240, Math.min(700, Number(data.animationDuration ?? 420)));
            } catch (error) {
                console.warn(`Unable to load dock preferences: ${error}`);
            }
            root.loaded = true;
        }
        onLoadFailed: root.loaded = true
    }
}
