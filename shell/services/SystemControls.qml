pragma Singleton
import QtQuick
import Quickshell
import qs.components

Singleton {
    id: root
    property var fields: []
    property var autostart: []
    property var units: []
    readonly property string error: backend.error
    readonly property bool busy: backend.busy
    readonly property var groups: [...new Set(fields.filter(f => f.available).map(f => f.group))]
    function reload(): void { backend.call(["list"], null, d => { if (!d.error) fields = d.fields; }); }
    property var pendingSets: ({})
    Timer {
        id: flushTimer
        interval: 60
        repeat: false
        onTriggered: {
            const keys = Object.keys(root.pendingSets);
            if (!keys.length) return;
            for (const key of keys) {
                const val = root.pendingSets[key];
                backend.call(["set", key, JSON.stringify(val)], null, d => {
                    if (d.error) root.reload();
                });
            }
            root.pendingSets = ({});
        }
    }
    function set(key: string, value: var): void {
        const next = [...root.fields];
        const idx = next.findIndex(f => f.key === key);
        if (idx >= 0) {
            next[idx] = Object.assign({}, next[idx], {value: value, overridden: true});
            root.fields = next;
        }
        root.pendingSets = Object.assign({}, root.pendingSets, {[key]: value});
        flushTimer.restart();
    }
    function reset(key: string): void { backend.call(["reset", key], null, d => { if (!d.error) reload(); }); }
    function reloadAutostart(): void { backend.call(["autostart"], null, d => { if (Array.isArray(d)) autostart = d; }); }
    function setAutostart(id: string, value: bool): void { backend.call(["autostart-set", id, value ? "true" : "false"], null, d => reloadAutostart()); }
    function addAutostart(name: string, command: string): void { backend.call(["autostart-add", name, command], null, d => reloadAutostart()); }
    function reloadUnits(): void { backend.call(["services"], null, d => { if (Array.isArray(d)) units = d; }); }
    function service(action: string, id: string): void { backend.call(["service", action, id], null, d => reloadUnits()); }
    FeatureBackend { id: backend; helper: "system_controls.py" }
}
