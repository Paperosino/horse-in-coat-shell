pragma Singleton
import QtQuick
import Quickshell

Singleton {
    id: root
    property var windowComponent: null
    property var pending: []

    function openPage(id: string): void { create(null, {pageId: id}); }
    function openPanelSettings(id: string): void { create(null, {pageId: "statusbar-layout", panelId: id}); }

    function finishLoading(): void {
        if (windowComponent.status === Component.Loading) return;
        const requests = pending;
        pending = [];
        if (windowComponent.status === Component.Error) {
            console.error("Cannot load settings:", windowComponent.errorString());
            windowComponent = null; // Allow retry after a transient read failure.
            return;
        }
        for (const request of requests)
            windowComponent.createObject(request.parent ?? root, request.props);
    }

    function create(parent: Item, props: var): void {
        pending = pending.concat([{parent: parent, props: props ?? {}}]);
        if (!windowComponent) {
            // A URL boundary keeps the complete settings component tree off
            // the desktop's startup compilation path. Compile on first use.
            windowComponent = Qt.createComponent(Qt.resolvedUrl("SettingsWindow.qml"), Component.Asynchronous);
            if (windowComponent.status === Component.Loading)
                windowComponent.statusChanged.connect(root.finishLoading);
        }
        finishLoading();
    }
}
