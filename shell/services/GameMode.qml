pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Io
import Hyprstack
import Hyprstack.Config
import Hyprstack.I18n
import Hyprstack.Services
import qs.services
Singleton {
    id: root
    property alias enabled: props.enabled
    property bool policyChange: false
    readonly property bool manualOverrideActive: props.manualOverride >= 0
    function resumeAutomatic(): void { props.manualOverride=-1; syncAutomatic(); }
    readonly property bool effectsSuspended: enabled && RuntimePerformance.settings.disableEffects
    readonly property bool pauseWallpapers: (enabled && RuntimePerformance.settings.pauseWallpapers) || RuntimePerformance.thermalLimited
    readonly property bool reduceDockMotion: (enabled && RuntimePerformance.settings.reduceDockMotion) || RuntimePerformance.thermalLimited
    // Effects is the sole live writer of blur and shadows. Optional tearing and
    // scanout never change the user's ordinary display/input configuration.
    readonly property var overrides: {
        const values = {};
        if (RuntimePerformance.settings.disableEffects) Object.assign(values, {
            "animations:enabled": 0, "general:gaps_in": 0, "general:gaps_out": 0,
            "general:border_size": 1, "decoration:rounding": 0
        });
        if (RuntimePerformance.settings.allowTearing) values["general:allow_tearing"] = 1;
        const scanout = RuntimePerformance.settings.directScanout;
        if (scanout) values["render:direct_scanout"] = scanout === 1 ? 2 : 1;
        return values;
    }
    function quietOn(screen:var):bool {
        if(!enabled||!screen)return false;
        const monitor=Hypr.monitorFor(screen);
        if(monitor?.lastIpcObject.specialWorkspace?.name)return false;
        return monitor?.activeWorkspace?.toplevels.values.some(t=>(t.lastIpcObject.fullscreen&2)!==0)??false;
    }
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
        const original = Object.assign({}, props.originalOptions), changes = {};
        for (const key of Object.keys(original)) if (!(key in overrides)) {
            changes[key] = original[key]; delete original[key];
        }
        for (const key of Object.keys(overrides)) {
            if (Hypr.options[key] === undefined) continue;
            if (!(key in original)) original[key] = Hypr.options[key];
            changes[key] = overrides[key];
        }
        props.originalOptions = original;
        Hypr.extras.applyOptions(changes);
    }
    function syncAutomatic(): void {
        policyChange = true;
        enabled = props.manualOverride === 1 || (props.manualOverride < 0 && RuntimePerformance.autoGame);
        policyChange = false;
    }
    onOverridesChanged: if (enabled) setDynamicConfs()
    onEnabledChanged: {
        if (!policyChange) props.manualOverride = enabled ? 1 : 0;
        if (enabled) setDynamicConfs();
        else {
            if (Object.keys(props.originalOptions).length) Hypr.extras.applyOptions(props.originalOptions);
            props.originalOptions = ({});
        }
        if (GlobalConfig.utilities.toasts.gameModeChanged)
            Toaster.toast(enabled ? Tr.tr("Game mode enabled") : Tr.tr("Game mode disabled"),
                enabled ? Tr.tr("Gaming preferences applied") : Tr.tr("Hyprland settings restored"), "gamepad");
    }
    PersistentProperties {
        id: props
        property bool enabled: false
        property int manualOverride: -1
        property int previousGamePid: 0
        property var originalOptions: ({})
        reloadableId: "gameMode"
    }
    Component.onCompleted: syncAutomatic()
    Connections {
        target: RuntimePerformance
        function onGameChanged(): void {
            if (RuntimePerformance.gamePid > 0 && props.previousGamePid !== RuntimePerformance.gamePid) {
                if (props.manualOverride === 0) props.manualOverride = -1;
                props.previousGamePid = RuntimePerformance.gamePid;
            }
            root.syncAutomatic();
        }
    }
    Connections {
        target: Hypr.extras
        function onOptionsChanged(): void { if (props.enabled && !Object.keys(props.originalOptions).length) root.setDynamicConfs(); }
        function onConfigOptionsReloaded(): void {
            if (props.enabled && root.captureOptions()) root.setDynamicConfs();
        }
    }
    IpcHandler {
        target: "gameMode"
        function isEnabled(): bool { return props.enabled; }
        function toggle(): void { props.enabled = !props.enabled; }
        function enable(): void { props.enabled = true; }
        function disable(): void { props.enabled = false; }
        function automatic(): void { root.resumeAutomatic(); }
    }
}
