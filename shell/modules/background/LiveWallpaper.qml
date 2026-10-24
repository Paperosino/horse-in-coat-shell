import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Services.UPower
import qs.services

Item {
    id: root
    required property ShellScreen screen
    readonly property string outputName: screen?.name ?? ""
    readonly property var settings: LiveWallpapers.forScreen(outputName)
    readonly property bool fullscreen: Hypr.layoutMode !== "canvas" && (Hypr.monitorFor(screen)?.activeWorkspace?.toplevels.values.some(t => t.lastIpcObject.fullscreen > 1) ?? false)
    readonly property url videoSource: LiveWallpapers.videoSource(settings)
    readonly property bool outputOff: Hypr.monitorFor(screen)?.lastIpcObject?.dpmsStatus === false
    readonly property bool engineWanted: !!root.screen && root.visible && root.settings.kind === "engine" && !videoSource.toString() && !!root.settings.source && !root.paused
    property int failures: 0
    property double failureWindow: Date.now()
    property double engineStarted: 0
    readonly property int restartSerial: LiveWallpapers.restartSerials[outputName] ?? 0
    onRestartSerialChanged: { failures = 0; retry.stop(); engine.running = false; restartEngine.restart(); }
    readonly property bool paused: outputOff || GameMode.pauseWallpapers || (settings.pauseBattery && UPower.onBattery) || (settings.pauseFullscreen && fullscreen)
    Loader {
        id: videoLoader
        anchors.fill: parent
        active: !!root.screen && root.visible && !!root.videoSource.toString()
        onLoaded: {
            item.outputName = root.outputName;
            item.settings = Qt.binding(() => root.settings);
            item.paused = Qt.binding(() => root.paused);
            item.restartSerial = Qt.binding(() => root.restartSerial);
        }
        // Required properties are supplied before construction.
        Component.onCompleted: if (active && !source) setSource("VideoWallpaper.qml", {settings: root.settings, paused: root.paused})
        onActiveChanged: if (active) setSource("VideoWallpaper.qml", {settings: root.settings, paused: root.paused})
    }
    Timer {
        id: restartEngine
        interval: 0
        onTriggered: if (root.engineWanted) engine.running = true
    }
    onEngineWantedChanged: {
        retry.stop();
        if (engineWanted) { failures = 0; restartEngine.restart(); }
        else engine.running = false;
    }
    Component.onCompleted: if (engineWanted) restartEngine.restart()
    function recover(): void {
        if (!engineWanted || retry.running) return;
        if (Date.now() - failureWindow > 600000) { failureWindow = Date.now(); failures = 0; }
        if (failures >= 6) { LiveWallpapers.playbackError = "Wallpaper renderer could not recover. Use Restart wallpaper to try again."; return; }
        failures++;
        retry.interval = Math.min(30000, 500 * Math.pow(2, failures));
        retry.start();
        engine.running = false;
    }
    Timer { id: retry; onTriggered: if (root.engineWanted) engine.running = true }
    // Process startup precedes the first mapped Wayland layer. Keep the static
    // fallback until the renderer actually has a surface on this output.
    Timer {
        interval: LiveWallpapers.engineRunning[root.outputName] ? 2000 : 300
        running: engine.running
        repeat: true
        onTriggered: if (!layers.running) layers.running = true
    }
    Process {
        id: layers
        command: ["hyprctl", "layers", "-j"]
        stdout: StdioCollector {
            onStreamFinished: {
                if (!engine.running) return;
                try {
                    const levels = JSON.parse(text)[root.outputName]?.levels ?? {};
                    const mapped = Object.values(levels).some(list => list.some(layer =>
                        layer.namespace === "linux-wallpaperengine" && Number(layer.pid) === Number(engine.processId)));
                    LiveWallpapers.reportEngine(root.outputName, mapped);
                    if (!mapped && Date.now() - root.engineStarted > 30000) root.recover();
                } catch (_) { LiveWallpapers.reportEngine(root.outputName, false); }
            }
        }
    }
    Process {
        id: engine
        command: LiveWallpapers.engineCommand(root.outputName)
        onCommandChanged: if (running) { running = false; restartEngine.restart(); }
        onRunningChanged: {
            if (!running) LiveWallpapers.reportEngine(root.outputName, false);
            else { root.engineStarted = Date.now(); if (!layers.running) layers.running = true; }
        }
        running: false
        stderr: StdioCollector { id: engineError }
        onExited: (code, status) => { if (root.engineWanted) { if (code !== 0 && code !== 15 && engineError.text) LiveWallpapers.playbackError = engineError.text.slice(-800); root.recover(); } }
    }
}
