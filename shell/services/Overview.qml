pragma Singleton

import QtQuick
import Quickshell
import Quickshell.Hyprland
import Quickshell.Io
import qs.components.misc
import qs.services
import "OverviewLayout.js" as Layout

Singleton {
    id: root

    property bool active: false
    property bool nativeStarted: false
    property string monitorName: ""
    property string selectedAddress: ""
    property int selectedWorkspace: 1
    property int originalWorkspace: 1
    property var snapshot: ({windows: [], workspaces: []})
    property string error: ""
    property int generation: 0
    readonly property bool stacking: snapshot.mode === "stacking"
    readonly property var screen: Screens.screens.find(s => s.name === monitorName) ?? null
    readonly property var layout: stacking
        ? Layout.stacking(snapshot, screen?.width ?? 1280, screen?.height ?? 720, selectedWorkspace)
        : Layout.scrolling(snapshot, screen?.width ?? 1280, screen?.height ?? 720, selectedAddress, selectedWorkspace)
    readonly property var frames: layout.frames
    readonly property var rows: layout.rows
    readonly property var selected: snapshot.windows?.find(w => w.address === selectedAddress) ?? null

    function toggle(): void {
        if (Hypr.layoutMode === "canvas") { Hypr.extras.message('eval hyprstack_layouts.canvas_action("overview")'); return; }
        if (active) {
            close(true);
            return;
        }
        const monitor = Hypr.focusedMonitor;
        if (!monitor)
            return;
        monitorName = monitor.name;
        selectedAddress = Hypr.activeToplevel?.lastIpcObject.address ?? "";
        selectedWorkspace = originalWorkspace = monitor.activeWorkspace?.id ?? 1;
        generation++;
        snapshot = {mode: Hypr.layoutMode, windows: [], workspaces: [], width: screen?.width ?? 1280, height: screen?.height ?? 720};
        nativeStarted = false;
        error = "";
        ShellState.closeDrawers();
        active = true;
        Hypr.extras.message("eval hyprstack_layouts.set_overview(true)");
        refresh();
    }

    property bool refreshPending: false
    property bool queryRunning:false

    function refresh(): void {
        if (!active)
            return;
        if (queryRunning) {
            refreshPending = true;
            return;
        }
        refreshPending = false;
        queryRunning = true;
        const requestedGeneration = generation;
        Hypr.extras.request(`j/repl return hyprstack_layouts.overview_snapshot(${Hypr.luaJsonText(monitorName)})`, (success,text) => {
            queryRunning = false;
            if (!active || requestedGeneration !== generation) { if (active) refresh(); return; }
            if (!success) {error=text;close(false);return;}
            acceptSnapshot(text);
        });
    }

    property string lastScenePayload: ""
    function applyScene(): void {
        if (!active || !snapshot.monitor)
            return;
        const world = stacking ? frames : layout.worldFrames;
        const colour = Colours.palette.m3primary;
        const scene = {dragMs: LayoutModes.config.overviewDragMs ?? 35, motionMs: LayoutModes.config.overviewMotionMs ?? 320, monitor: monitorName, mode: snapshot.mode, selected: selectedAddress,
            workspace: selectedWorkspace, originalWorkspace: originalWorkspace,
            camera: layout.camera ?? {zoom: 1, x: 0, y: 0}, originCamera: layout.originCamera ?? {zoom: 1, x: 0, y: 0},
            worldRows: layout.worldRows ?? [], colour: [colour.r, colour.g, colour.b], wallpaper: Wallpapers.current,
            windows: snapshot.windows.map(w => Object.assign({}, w, {
                frame: frames.find(f => f.address === w.address),
                world: world.find(f => f.address === w.address)
            }))};
        const payload = JSON.stringify(scene);
        if (nativeStarted && payload === lastScenePayload) return;
        lastScenePayload = payload;
        Hypr.extras.message(`eval hyprstack_layouts.overview_scene("show", ${Hypr.luaJsonText(payload)})`);
        nativeStarted = true;
    }

    function close(activateSelection: bool): void {
        if (!active)
            return;
        // Activate behind the still-rendered overview, then zoom into the new
        // native viewport. There is no intermediate return to the old desktop.
        const activate = activateSelection
            ? `hyprstack_layouts.overview_activate(${JSON.stringify(selectedAddress)}, ${JSON.stringify(selected?.identity ?? "")}, ${selectedWorkspace}, ${JSON.stringify(monitorName)}); ` : "";
        Hypr.extras.message(`eval ${activate}hyprstack_layouts.overview_scene("close", ${activateSelection}); hyprstack_layouts.set_overview(false)`);
        active = false;
        nativeStarted = false;
    }

    function navigate(direction: string): void {
        if (!active)
            return;
        const next = Layout.navigate(snapshot, selectedAddress, selectedWorkspace, direction, frames);
        selectedAddress = next.address;
        selectedWorkspace = next.workspace;
        applyScene();
    }

    function select(address: string): void {
        const window = snapshot.windows?.find(w => w.address === address);
        if (!active || !window)
            return;
        selectedAddress = address;
        selectedWorkspace = window.workspace;
        applyScene();
    }

    function selectWorkspace(workspace: int): void {
        selectedWorkspace = workspace;
        selectedAddress = snapshot.windows?.find(w => w.workspace === workspace)?.address ?? "";
        applyScene();
    }

    function cycle(backwards: bool): void {
        const windows = snapshot.windows ?? [];
        if (!active || !windows.length)
            return;
        const index = windows.findIndex(w => w.address === selectedAddress);
        select(windows[(index + (backwards ? windows.length - 1 : 1)) % windows.length].address);
    }

    function closeSelected(): void {
        if (!active || !selected)
            return;
        Hypr.extras.message(`eval hyprstack_layouts.overview_close(${JSON.stringify(selectedAddress)}, ${JSON.stringify(selected.identity)}, ${JSON.stringify(monitorName)})`);
    }

    function handleDragDrop(input: var): void {
        const source = input.source;
        const target = input.target ?? "";
        const ws = input.workspace;
        Hypr.extras.message(`eval if hyprstack_layouts and hyprstack_layouts.overview_drag_drop then hyprstack_layouts.overview_drag_drop(${JSON.stringify(source)}, ${JSON.stringify(target)}, ${JSON.stringify(ws)}, ${JSON.stringify(monitorName)}) end`);
        refresh();
    }

    Component.onCompleted: Hypr.extras.message('eval hyprstack_layouts.overview_scene("reset"); hyprstack_layouts.set_overview(false)')
    onScreenChanged: if (active && !screen) close(false)

    function acceptSnapshot(text:string):void {
                try {
                    const state = JSON.parse(text.trim());
                    if (!state.monitor || (root.nativeStarted && !state.renderer?.active)) {
                        root.close(false);
                        return;
                    }
                    // Lua represents empty arrays as objects.
                    state.windows = Array.isArray(state.windows) ? state.windows : [];
                    state.workspaces = Array.isArray(state.workspaces) ? state.workspaces : [];
                    const previous = root.snapshot.windows ?? [];
                    const previousIndex = previous.findIndex(w => w.address === root.selectedAddress);
                    root.snapshot = state;
                    const ids = root.stacking ? state.workspaces : Layout.workspaceIds(state);
                    if (ids.length && !ids.includes(root.selectedWorkspace))
                        root.selectedWorkspace = ids.reduce((best, id) => Math.abs(id - root.selectedWorkspace) < Math.abs(best - root.selectedWorkspace) ? id : best, ids[0]);
                    if (!state.windows.some(w => w.address === root.selectedAddress)) {
                        const neighbours = previous.slice(previousIndex + 1).concat(previous.slice(0, Math.max(0, previousIndex)).reverse());
                        const next = neighbours.find(w => w.workspace === root.selectedWorkspace && state.windows.some(live => live.address === w.address));
                        root.selectedAddress = next?.address ?? state.windows.find(w => w.workspace === root.selectedWorkspace)?.address ?? "";
                    }
                    root.error = "";
                    if (state.input?.action) {
                        if (state.input.action === "accept") {
                            root.selectedAddress = state.input.address ?? "";
                            root.selectedWorkspace = state.input.workspace ?? root.selectedWorkspace;
                            root.applyScene();
                            root.close(true);
                        } else if (state.input.action === "drag_drop") {
                            if (state.input.applied) {
                                root.selectedAddress = state.input.source ?? root.selectedAddress;
                                root.selectedWorkspace = state.input.workspace ?? root.selectedWorkspace;
                            }
                            root.applyScene();
                        } else root.close(false);
                    } else root.applyScene();
                } catch (e) {
                    root.error = String(e);
                    console.warn("Overview snapshot:", text.trim(), e);
                    root.close(false);
                } finally {
                    if (root.refreshPending) {
                        root.refreshPending = false;
                        root.refresh();
                    }
                }
    }

    // Retain crash recovery without polling window snapshots or spawning hyprctl.
    Timer {interval:750;repeat:true;running:root.active;onTriggered:Hypr.extras.message('eval hyprstack_layouts.overview_scene("heartbeat")')}
    Timer {id:refreshDelay;interval:35;onTriggered:root.refresh()}

    Connections {
        target: Hypr
        function onConfigReloaded(): void { root.refresh(); }
    }
    Connections {
        target: Hyprland
        function onRawEvent(event: HyprlandEvent): void {
            if (root.active && ["openwindow","closewindow","movewindow","movewindowv2","changefloatingmode","fullscreen","windowtitle","windowtitlev2","workspace","workspacev2","monitoradded","monitorremoved"].includes(event.name))
                refreshDelay.restart();
        }
    }

    CustomShortcut { name: "overview"; description: "Toggle window overview"; onPressed: root.toggle() }
    CustomShortcut { name: "overviewOpen"; description: "Open window overview"; onPressed: if (!root.active) root.toggle() }
    CustomShortcut { name: "overviewH"; description: "Overview left"; onPressed: root.navigate("H") }
    CustomShortcut { name: "overviewJ"; description: "Overview down"; onPressed: root.navigate("J") }
    CustomShortcut { name: "overviewK"; description: "Overview up"; onPressed: root.navigate("K") }
    CustomShortcut { name: "overviewL"; description: "Overview right"; onPressed: root.navigate("L") }
    CustomShortcut { name: "overviewCancel"; description: "Cancel overview"; onPressed: root.close(false) }
    CustomShortcut { name: "overviewAccept"; description: "Activate overview selection"; onPressed: root.close(true) }
    CustomShortcut { name: "overviewCycle"; description: "Next overview window"; onPressed: root.cycle(false) }
    CustomShortcut { name: "overviewBackcycle"; description: "Previous overview window"; onPressed: root.cycle(true) }
    CustomShortcut { name: "overviewClose"; description: "Close selected overview window"; onPressed: root.closeSelected() }
    CustomShortcut { name: "overviewPointer"; description: "Overview pointer selection"; onPressed: root.refresh() }

    IpcHandler {
        target: "overview"
        function toggle(): void { root.toggle(); }
        function close(): void { root.close(false); }
        function navigate(direction: string): void { root.navigate(direction.toUpperCase()); }
        function activate(): void { root.close(true); }
        function closeSelected(): void { root.closeSelected(); }
        function state(): string {
            return JSON.stringify({active: root.active, monitor: root.monitorName,
                mode: root.snapshot.mode, selected: root.selectedAddress, workspace: root.selectedWorkspace,
                error: root.error, frames: root.frames, rows: root.rows, windows: root.snapshot.windows,
                renderer: root.snapshot.renderer ?? {active: false}});
        }
    }
}
