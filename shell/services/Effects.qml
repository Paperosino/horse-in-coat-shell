pragma Singleton

import QtQuick
import Quickshell
import Quickshell.Io
import Hyprstack.Services
import qs.utils

Singleton {
    id: root

    property bool blurEnabled: true
    readonly property bool effectiveBlurEnabled: blurEnabled && !GameMode.effectsSuspended && RuntimePerformance.quality > 0
    readonly property real effectiveShadowSize: shadowSize * (RuntimePerformance.quality === 1 ? 0.65 : 1)
    property bool windowShadows: true
    property bool uiShadows: true
    property int shadowSize: 18
    property real shadowOpacity: 0.35
    readonly property bool uiShadowsEnabled: uiShadows && shadowSize > 0 && shadowOpacity > 0 && !GameMode.effectsSuspended && RuntimePerformance.quality > 0
    property bool loaded: false

    function setBlurEnabled(enabled: bool): void {
        set("blur", enabled);
    }

    function set(option: string, value: var): void {
        if (!loaded) return;
        if (option === "blur") blurEnabled = !!value;
        else if (option === "windowShadows") windowShadows = !!value;
        else if (option === "uiShadows") uiShadows = !!value;
        else if (option === "shadowSize") shadowSize = Math.max(0, Math.min(60, Math.round(value)));
        else if (option === "shadowOpacity") shadowOpacity = Math.max(0, Math.min(1, value));
        else return;
        storage.setText(JSON.stringify({blur: blurEnabled, windowShadows: windowShadows,
            uiShadows: uiShadows, shadowSize: shadowSize, shadowOpacity: shadowOpacity}));
        apply();
    }

    function apply(): void {
        if (!loaded) return;
        Hypr.extras.applyOptions({"decoration:blur:enabled": effectiveBlurEnabled ? 1 : 0});
        if (Hypr.usingLua)
            Hypr.extras.message(`eval if hyprstack_layouts then hyprstack_layouts.shadows({windowShadows=${windowShadows && !GameMode.effectsSuspended && RuntimePerformance.quality > 0},shadowSize=${effectiveShadowSize},shadowOpacity=${shadowOpacity}}) end`);
    }

    FileView {
        id: storage
        path: `${Paths.config}/effects.json`
        printErrors: false
        watchChanges: true
        onFileChanged: reload()
        onLoaded: {
            try {
                const data = JSON.parse(text());
                root.blurEnabled = data.blur !== false;
                root.windowShadows = data.windowShadows !== false;
                root.uiShadows = data.uiShadows !== false;
                root.shadowSize = Math.max(0, Math.min(60, Math.round(data.shadowSize ?? 18)));
                root.shadowOpacity = Math.max(0, Math.min(1, data.shadowOpacity ?? 0.35));
            } catch (error) {
                console.warn(`Unable to load effect preferences: ${error}`);
            }
            root.loaded = true;
            root.apply();
        }
        onLoadFailed: { root.loaded = true; root.apply(); }
    }

    onEffectiveBlurEnabledChanged: apply()
    onEffectiveShadowSizeChanged: apply()
    Connections { target: RuntimePerformance; function onStatusChanged(): void { root.applyQualityShadows(); } }
    property int appliedQuality: -1
    function applyQualityShadows(): void { if (appliedQuality !== RuntimePerformance.quality) { appliedQuality=RuntimePerformance.quality; apply(); } }

    Connections {
        target: Hypr
        function onConfigReloaded(): void { root.apply(); }
    }

    Connections {
        target: GameMode
        function onEffectsSuspendedChanged(): void { root.apply(); }
    }
}
