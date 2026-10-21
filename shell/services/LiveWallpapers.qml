pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Io
import Hyprstack.Config
import Hyprstack.Services
import qs.components
import qs.utils

Singleton {
    id: root
    property var config: ({defaults: {}, outputs: {}, workshopPaths: []})
    property var entries: []
    property var capabilities: ({})
    property string playbackError: ""
    readonly property string error: backend.error || Object.values(videoStates).find(s => s.error)?.error || playbackError
    readonly property bool busy: backend.busy
    property var videoStates: ({})
    function reportVideo(name: string, state: var): void { videoStates = Object.assign({}, videoStates, {[name]: state}); }
    property var engineRunning: ({})
    function reportEngine(name: string, value: bool): void { engineRunning = Object.assign({}, engineRunning, {[name]: value}); }
    property var restartSerials: ({})
    function restart(name: string): void {
        playbackError = "";
        restartSerials = Object.assign({}, restartSerials, {[name]: (restartSerials[name] ?? 0) + 1});
    }
    function videoSource(settings: var): url {
        return settings.kind === "video" || settings.kind === "engine" ? DesktopIntegration.wallpaperVideo(settings.source) : "";
    }
    IpcHandler {
        target: "wallpapers"
        function status(): string { return JSON.stringify({videos: root.videoStates, engines: root.engineRunning, error: root.error}); }
        function restart(output: string): void {
            const names = output ? [output] : Screens.screens.map(s => s.name);
            for (const name of names) root.restart(name);
        }
    }
    property var elapsed: ({})
    property var lastItems: ({})
    readonly property string helper: Paths.toLocalFile(Qt.resolvedUrl("../assets/live_wallpapers.py"))
    function forScreen(name: string): var {
        return Object.assign({kind: "static", source: "", muted: true, volume: 15, fps: 30, scaling: "fill", pauseFullscreen: true, pauseBattery: true,
            disableMouse: false, disableParticles: false, disableParallax: false, syncColors: true, properties: {}, playlist: [], cycleMinutes: 15, shuffle: false}, config.defaults, config.outputs?.[name]);
    }
    function reloadLibrary(): void { backend.call(["library"], null, d => { if (!d.error) { entries = d.entries; capabilities = d; } }); }
    function setPaths(paths: var): void { backend.call(["paths"], paths, d => { if (!d.error) { config = d; reloadLibrary(); } }); }
    function save(name: string, settings: var): void {
        playbackError = "";
        backend.call(["save", name], settings, d => {
            if (d.error) return;
            config = d;
            elapsed[name] = 0;
            const item = entries.find(e => e.path === settings.source);
            if (settings.kind === "engine" && settings.syncColors && item?.preview) Wallpapers.setWallpaper(item.preview);
        });
    }
    function engineCommand(name: string): var {
        const c = forScreen(name);
        const command = ["linux-wallpaperengine", "--screen-root", name, "--bg", c.source,
            "--scaling", c.scaling, "--layer", "background", "--fps", String(c.fps)];
        command.push(...(c.muted ? ["--silent"] : ["--volume", String(c.volume)]));
        // The shell owns pause policy. Native fullscreen flags are not a
        // reliable occlusion test while a canvas camera transforms windows.
        command.push("--no-fullscreen-pause");
        if (c.disableMouse) command.push("--disable-mouse");
        if (c.disableParticles) command.push("--disable-particles");
        if (c.disableParallax) command.push("--disable-parallax");
        for (const [key, value] of Object.entries(c.properties ?? {})) command.push("--set-property", key + "=" + (typeof value === "boolean" ? (value ? "1" : "0") : Array.isArray(value) ? value.join(" ") : String(value)));
        return command;
    }
    Component.onCompleted: backend.call(["config"], null, d => { if (!d.error) config = d; });
    FeatureBackend { id: backend; helper: "live_wallpapers.py" }
    FileView {
        path: `${Paths.config}/live-wallpapers.json`
        watchChanges: true
        printErrors: false
        onFileChanged: reload()
        onLoaded: { try { root.config = JSON.parse(text()); } catch (e) { root.playbackError = String(e); } }
    }
    Timer {
        interval: 60000
        repeat: true
        running: Object.values(root.config.outputs ?? {}).some(c => c.playlist?.length > 1)
        onTriggered: {
            for (const name of Object.keys(root.config.outputs ?? {})) {
                const c = root.forScreen(name);
                if (c.playlist.length < 2) continue;
                root.elapsed[name] = (root.elapsed[name] ?? 0) + 1;
                if (root.elapsed[name] < c.cycleMinutes) continue;
                root.elapsed[name] = 0;
                const previous = c.playlist.indexOf(c.source);
                const next = c.shuffle ? (previous + 1 + Math.floor(Math.random() * (c.playlist.length - 1))) % c.playlist.length : (previous + 1) % c.playlist.length;
                root.save(name, Object.assign({}, c, {source: c.playlist[next]}));
            }
        }
    }
}
