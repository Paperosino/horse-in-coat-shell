pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Services.UPower
import Hyprstack.Services
import qs.services
Singleton {
    id: root
    property bool locked: false
    property string lastWindowSignature: ""
    readonly property var preferences: RuntimePerformance.settings
    readonly property int quality: RuntimePerformance.quality
    readonly property bool thermalLimited: RuntimePerformance.thermalLimited
    function observe(): void {
        const ipc = Hypr.activeToplevel?.lastIpcObject ?? {};
        const window = {address:ipc.address??"",pid:ipc.pid??0,class:ipc.class??"",fullscreen:ipc.fullscreen??0,mapped:ipc.mapped??false};
        const signature=JSON.stringify(window);
        if(signature===lastWindowSignature)return;
        lastWindowSignature=signature;
        const entry = preferences.prefetch ? ApplicationCatalogue.heuristicLookup(window.class ?? "") : null;
        const executable = entry?.command?.[0] ?? "";
        RuntimePerformance.observeWindow(window, entry?.id ?? "", executable);
    }
    function syncSession(): void { RuntimePerformance.setSessionState(GameMode.enabled, UPower.onBattery, locked); }
    onLockedChanged: { syncSession(); observe(); }
    Component.onCompleted: { observe(); syncSession(); }
    Connections { target: Hypr; function onActiveToplevelChanged(): void { observeDelay.restart(); } }
    Connections { target: Hypr.activeToplevel; function onLastIpcObjectChanged(): void { observeDelay.restart(); } }
    Connections { target: RuntimePerformance; function onSettingsChanged(): void { root.lastWindowSignature=""; root.observe(); root.syncSession(); } }
    Connections { target: UPower; function onOnBatteryChanged(): void { root.syncSession(); } }
    Connections { target: GameMode; function onEnabledChanged(): void { root.syncSession(); } }
    Timer { id: observeDelay; interval: 50; onTriggered: root.observe() }
    IpcHandler {
        target: "performance"
        function status(): string { return JSON.stringify(RuntimePerformance.status); }
        function settings(): string { return JSON.stringify(RuntimePerformance.settings); }
    }
}
