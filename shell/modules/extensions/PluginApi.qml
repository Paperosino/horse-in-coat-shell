import QtQuick
import Quickshell
import qs.services
import qs.modules.nexus

QtObject {
    id: root
    required property string pluginId
    readonly property var manifest: Plugins.byId(pluginId) ?? ({})
    readonly property var pluginSettings: manifest.settings ?? ({})
    readonly property var settings: pluginSettings
    readonly property string pluginDir: manifest.path ?? ""
    readonly property string pluginDataDir: `${Quickshell.env("XDG_STATE_HOME") || Quickshell.env("HOME") + "/.local/state"}/hics/plugins/${pluginId}`
    readonly property var isolatedState: Plugins.isolatedStates[pluginId] ?? ({slots:{}})
    function sendAction(action: string, value: var): void {Plugins.workerAction(pluginId,action,value);}
    property var mainInstance: null
    property var barWidget: null
    function saveSettings(value = null): void { Plugins.saveSettings(pluginId, value ?? pluginSettings); }
    function setSetting(key: string, value: var): void { Plugins.saveSettings(pluginId, Object.assign({}, pluginSettings, {[key]: value})); }
    function tr(key: string, substitutions = {}): string {
        let text = key;
        for (const [k, v] of Object.entries(substitutions)) text = text.replace("{" + k + "}", String(v));
        return text;
    }
    function openPanel(screen = null): void { Plugins.open(pluginId); }
    function togglePanel(screen = null): void { openPanel(screen); }
    function closePanel(screen = null): void {}
    function openSettings(): void { Plugins.open(pluginId); }
}
