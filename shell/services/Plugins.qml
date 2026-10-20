pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Io
import qs.utils
import qs.components
import qs.modules.nexus

Singleton {
    id: root
    property var plugins: []
    property var errors: []
    property var removed: []
    property var runtimeErrors: ({})
    property var contexts: ({})
    property string selectedId: ""
    property int revision: 0
    readonly property var enabled: plugins.filter(p => p.enabled)
    readonly property bool busy: backend.busy
    readonly property string error: backend.error
    function accept(d: var): void { if (d.error) return; plugins = d.plugins; removed = d.removed ?? []; errors = d.errors; }
    function reloadCode(): void { runtimeErrors = {}; revision++; reload(); }
    function reload(): void { backend.call(["list"], null, accept); }
    function setEnabled(id: string, value: bool): void { backend.call([value ? "enable" : "disable", id], null, d => { accept(d); }); }
    function update(path: string): void { backend.call(["update", path], null, accept); }
    function rollback(id: string): void { backend.call(["rollback", id], null, d => { accept(d); revision++; }); }
    function restore(id: string): void { backend.call(["restore", id], null, accept); }
    function install(path: string): void { backend.call(["install", path], null, accept); }
    function remove(id: string): void { backend.call(["remove", id], null, d => { accept(d); }); }
    function saveSettings(id: string, value: var): void { backend.call(["settings", id], value, accept); }
    function byId(id: string): var { return plugins.find(p => p.id === id) ?? null; }
    function apiFor(id: string): var { return contexts[id] ?? null; }
    function registerApi(id: string, api: var): void { contexts = Object.assign({}, contexts, {[id]: api}); }
    function unregisterApi(id: string): void { const next = Object.assign({}, contexts); delete next[id]; contexts = next; }
    function reportError(id: string, error: string): void { runtimeErrors = Object.assign({}, runtimeErrors, {[id]: error}); }
    function open(id: string): void { selectedId = id; WindowFactory.openPage("plugins"); }
    Component.onCompleted: reload()
    IpcHandler {
        target: "plugins"
        function refresh(): void { root.reload(); }
        function reload(): void { root.reloadCode(); }
        function list(): string { return JSON.stringify(root.plugins.map(p => ({id: p.id, enabled: p.enabled, compatible: p.compatible}))); }
        function enable(id: string): void { root.setEnabled(id, true); }
        function disable(id: string): void { root.setEnabled(id, false); }
    }
    FileView { path: `${Paths.config}/plugins.json`; printErrors: false; watchChanges: true; onFileChanged: root.reload() }
    FeatureBackend { id: backend; helper: "plugin_manager.py" }
}
