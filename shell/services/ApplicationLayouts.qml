pragma Singleton
import QtQuick
import Quickshell
import Hyprstack.Config
Singleton {
    id: root
    property var backend: Hypr
    property var memory: ({})
    property string previousApp: ""
    property int previousIndex: -1
    property int expectedIndex: -1
    property string fingerprint: ""
    readonly property bool enabled: GlobalConfig.utilities.comfort.applicationLayouts
    function currentIndex(): int {
        const index = backend.keyboard?.lastIpcObject?.active_layout_index;
        if (index !== undefined) return Number(index);
        return String(backend.keyboard?.layout ?? "").split(",").indexOf(backend.kbLayout);
    }
    function remember(app, index): void {
        if (!app || index < 0) return;
        const values = Object.assign({}, memory, {[app]:index});
        const keys = Object.keys(values);
        if (keys.length > 128) delete values[keys[0]];
        memory = values;
    }
    function clear(): void { memory=({}); previousApp=""; previousIndex=-1; expectedIndex=-1; pending.stop(); }
    function focus(): void {
        if (!enabled || !backend.keyboard) { clear(); return; }
        const signature = JSON.stringify([backend.keyboard.layout,backend.keyboard.lastIpcObject?.variant]);
        if (signature !== fingerprint) { clear(); fingerprint=signature; }
        const app = String(backend.activeToplevel?.lastIpcObject?.class ?? "").slice(0,256);
        if (!app || app===previousApp) return;
        if (expectedIndex < 0) remember(previousApp, previousIndex);
        previousApp=app; previousIndex=currentIndex(); expectedIndex=-1; pending.stop();
        const target=memory[app];
        if (typeof target!=="number" || target===previousIndex || target<0 || target>=backend.keyboard.layout.split(",").length) return;
        expectedIndex=target;
        backend.extras.request(`switchxkblayout all ${target}`, (ok,response)=>{
            if (!ok || response.trim()!=="ok") { expectedIndex=-1; previousIndex=currentIndex(); }
        });
        pending.restart();
    }
    onEnabledChanged: { clear(); if(enabled)focus(); }
    Timer { id:pending; interval:500; onTriggered:{root.previousIndex=root.currentIndex();root.expectedIndex=-1;} }
    Connections {
        enabled:root.enabled
        target:root.backend
        function onActiveToplevelChanged():void {Qt.callLater(root.focus);}
        function onKbLayoutFullChanged():void {
            if (!root.enabled) return;
            const index=root.currentIndex();
            if(root.expectedIndex>=0 && index!==root.expectedIndex)return;
            root.expectedIndex=-1;pending.stop();root.previousIndex=index;root.remember(root.previousApp,index);
        }
        function onKeyboardChanged():void {root.clear();Qt.callLater(root.focus);}
    }
    Component.onCompleted:if(enabled)focus()
}
