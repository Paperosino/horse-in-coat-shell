import QtQuick
import Quickshell
import qs.services
// Register bridge modules before loading entry points outside the shell tree.
import qs.Commons
import qs.Services
import qs.Widgets

Loader {
    id: root
    required property string pluginId
    required property string slot
    property var api: Plugins.apiFor(pluginId)
    readonly property var entry: Plugins.byId(pluginId)?.entryPoints?.[slot] ?? null
    readonly property int generation: Plugins.revision
    readonly property string entryUrl: entry ? entry.url.replace(/^file:/, "qs:") + "?revision=" + generation : ""
    asynchronous: true
    active: !!entry && !!api
    function load(): void {
        if (!active) { source = ""; return; }
        if(entry.format==="declarative"){sourceComponent=declarativeView;return;}
        sourceComponent=undefined;
        const props = entry.property ? {[entry.property]: api} : {};
        for (const property of entry.requiredProperties ?? []) {
            if (property === "screen") props.screen = QsWindow.window?.screen ?? null;
            if (property === "screenName") props.screenName = QsWindow.window?.screen?.name ?? "";
            if (property === "pluginId") props.pluginId = pluginId;
        }
        setSource(entryUrl, props);
    }
    Component {id:declarativeView;DeclarativePluginView {pluginApi:root.api;slot:root.slot}}
    onEntryUrlChanged: Qt.callLater(load)
    onApiChanged: Qt.callLater(load)
    Component.onCompleted: Qt.callLater(load)
    onStatusChanged: if (status === Loader.Error) Plugins.reportError(pluginId, "Unable to load " + slot + ": " + entry?.url)
}
