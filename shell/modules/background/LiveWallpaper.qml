import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Services.UPower
import qs.services

Item {
    id: root
    required property ShellScreen screen
    readonly property var settings: LiveWallpapers.forScreen(screen.name)
    readonly property bool fullscreen: Hypr.layoutMode !== "canvas" && (Hypr.monitorFor(screen)?.activeWorkspace?.toplevels.values.some(t => t.lastIpcObject.fullscreen > 1) ?? false)
    readonly property bool paused: GameMode.enabled || (settings.pauseBattery && UPower.onBattery) || (settings.pauseFullscreen && fullscreen)
    Loader {
        id: videoLoader
        anchors.fill: parent
        active: root.visible && root.settings.kind === "video" && root.settings.source !== ""
        onLoaded: {
            item.settings = Qt.binding(() => root.settings);
            item.paused = Qt.binding(() => root.paused);
        }
        // Required properties are supplied before construction.
        Component.onCompleted: if (active && !source) setSource("VideoWallpaper.qml", {settings: root.settings, paused: root.paused})
        onActiveChanged: if (active) setSource("VideoWallpaper.qml", {settings: root.settings, paused: root.paused})
    }
    Timer {
        id: restartEngine
        interval: 0
        onTriggered: engine.running = Qt.binding(() => root.visible && root.settings.kind === "engine" && !!root.settings.source && !root.paused)
    }
    // Process startup precedes the first mapped Wayland layer. Keep the static
    // fallback until the renderer actually has a surface on this output.
    Timer {
        interval: LiveWallpapers.engineRunning[root.screen.name] ? 2000 : 300
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
                    const levels = JSON.parse(text)[root.screen.name]?.levels ?? {};
                    const mapped = Object.values(levels).some(list => list.some(layer =>
                        layer.namespace === "linux-wallpaperengine" && Number(layer.pid) === Number(engine.processId)));
                    LiveWallpapers.reportEngine(root.screen.name, mapped);
                } catch (_) { LiveWallpapers.reportEngine(root.screen.name, false); }
            }
        }
    }
    Process {
        id: engine
        command: LiveWallpapers.engineCommand(root.screen.name)
        onCommandChanged: if (running) { running = false; restartEngine.restart(); }
        onRunningChanged: {
            if (!running) LiveWallpapers.reportEngine(root.screen.name, false);
            else if (!layers.running) layers.running = true;
        }
        running: root.visible && root.settings.kind === "engine" && !!root.settings.source && !root.paused
        stderr: StdioCollector { id: engineError }
        onExited: (code, status) => { if (code !== 0 && code !== 15 && engineError.text) LiveWallpapers.playbackError = engineError.text.slice(-800); }
    }
}
