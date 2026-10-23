pragma Singleton

import QtQuick
import Quickshell
import Quickshell.Io
import Hyprstack
import Hyprstack.Config
import Hyprstack.I18n
import qs.services

Singleton {
    id: root

    property alias enabled: props.enabled

    // Effects owns shadow policy, including its response to game mode.
    // Keep one writer per option across config reload and mode transitions.
    readonly property var overrides: ({
        "animations:enabled": 0,
        "decoration:blur:enabled": 0,
        "general:gaps_in": 0,
        "general:gaps_out": 0,
        "general:border_size": 1,
        "decoration:rounding": 0,
        "general:allow_tearing": 1
    })

    function captureOptions(): bool {
        const original = {};
        for (const key of Object.keys(overrides)) {
            if (Hypr.options[key] === undefined) return false;
            original[key] = Hypr.options[key];
        }
        props.originalOptions = original;
        return true;
    }

    function setDynamicConfs(): void {
        if (!Object.keys(props.originalOptions).length && !captureOptions()) return;
        Hypr.extras.applyOptions(overrides);
    }

    onEnabledChanged: {
        if (enabled) {
            setDynamicConfs();
            if (GlobalConfig.utilities.toasts.gameModeChanged)
                Toaster.toast(Tr.tr("Game mode enabled"), Tr.tr("Disabled Hyprland animations, blur, gaps and shadows"), "gamepad");
        } else {
            if (Object.keys(props.originalOptions).length)
                Hypr.extras.applyOptions(props.originalOptions);
            props.originalOptions = ({});
            if (GlobalConfig.utilities.toasts.gameModeChanged)
                Toaster.toast(Tr.tr("Game mode disabled"), Tr.tr("Hyprland settings restored"), "gamepad");
        }
    }

    PersistentProperties {
        id: props

        // Disabling animations for accessibility does not enable game mode.
        property bool enabled: false
        property var originalOptions: ({})

        reloadableId: "gameMode"
    }

    Connections {
        target: Hypr.extras
        function onOptionsChanged(): void {
            if (props.enabled && !Object.keys(props.originalOptions).length)
                root.setDynamicConfs();
        }
        // Wait for the new configuration snapshot, rather than racing its
        // asynchronous read with another batch of game-mode overrides.
        function onConfigOptionsReloaded(): void {
            if (props.enabled && root.captureOptions()) root.setDynamicConfs();
        }
    }

    IpcHandler {
        function isEnabled(): bool {
            return props.enabled;
        }

        function toggle(): void {
            props.enabled = !props.enabled;
        }

        function enable(): void {
            props.enabled = true;
        }

        function disable(): void {
            props.enabled = false;
        }

        target: "gameMode"
    }
}
