pragma ComponentBehavior: Bound

import QtQuick
import Quickshell
import Hyprstack.I18n
import Hyprstack.Services
import qs.services

// The portal query and window-close requests are coordinated here; the
// non-modal dialog never makes a termination decision on its own.
Scope {
    id: root
    required property bool locked
    readonly property alias dialogWindow: dialog
    property bool closingWindows: false
    property bool preparing: false
    property bool polling: false
    property int generation: 0
    property int emptyPasses: 0
    property string windowError: ""
    property var originalWindows: []
    property var remainingWindows: []

    function readWindows(done): void {
        Hypr.extras.request("j/clients", (success, text) => {
            if (!success) { done(false, []); return; }
            try {
                const clients = JSON.parse(text);
                if (!Array.isArray(clients)) { done(false, []); return; }
                done(true, clients.filter(w => !!w.mapped && w.class !== "org.hics.Shell"));
            } catch (error) { done(false, []); }
        });
    }
    function start(): void {
        if (root.locked || root.preparing || LogoutController.active || LogoutController.busy) return;
        root.preparing = true;
        root.polling = false;
        const generation = ++root.generation;
        root.readWindows((success, clients) => {
            if (generation !== root.generation) return;
            root.preparing = false;
            if (root.locked) return;
            root.originalWindows = clients;
            root.remainingWindows = clients;
            root.windowError = success ? "" : Tr.tr("Could not read application windows");
            root.closingWindows = false;
            root.emptyPasses = 0;
            SessionManager.checkpointLogout();
            LogoutController.request();
        });
    }
    function refresh(): void {
        if (!LogoutController.active || root.locked || root.polling) return;
        root.polling = true;
        const generation = root.generation;
        root.readWindows((success, clients) => {
            if (generation !== root.generation) return;
            root.polling = false;
            if (!LogoutController.active || root.locked) return;
            if (!success) {
                root.windowError = Tr.tr("Could not read application windows");
                root.emptyPasses = 0;
                return;
            }
            root.windowError = "";
            root.remainingWindows = clients;
            if (!LogoutController.ready || LogoutController.busy) { root.emptyPasses = 0; return; }
            if (!root.closingWindows) {
                root.closingWindows = true;
                for (const w of root.originalWindows) {
                    if (!w.address || !w.stableId || !clients.some(c => c.address === w.address && c.stableId === w.stableId)) continue;
                    Hypr.extras.message(`eval hyprstack_layouts.action("close", ${JSON.stringify(w.address)}, ${JSON.stringify(w.stableId)})`);
                }
                root.emptyPasses = 0;
                return;
            }
            if (clients.length) { root.emptyPasses = 0; return; }
            // Only a fresh successful compositor snapshot can permit commit.
            if (++root.emptyPasses >= 3) LogoutController.commit();
        });
    }
    function blockerModel(): var {
        const items = LogoutController.blockers.map(b => ({
            name: String(b.app_id || Tr.tr("Unknown application")),
            reason: b.pending ? Tr.tr("Waiting for the application to respond") : String(b.reason || "")
        }));
        if (LogoutController.error) items.push({name: Tr.tr("Could not check applications"), reason: LogoutController.error});
        if (root.windowError) items.push({name: root.windowError, reason: ""});
        for (const ipc of root.remainingWindows) {
            items.push({name: String(ipc.title || ipc.class || Tr.tr("Unknown application")),
                        reason: Tr.tr("Waiting for the window to close")});
        }
        return items;
    }
    onLockedChanged: { if (locked) { ++root.generation; root.preparing = false; root.polling = false; } LogoutController.locked = locked; }
    Component.onCompleted: LogoutController.locked = root.locked

    Connections {
        target: SessionManager
        function onLogoutRequested(): void { root.start(); }
        function onTerminateFailed(reason: string): void { LogoutController.terminationFailed(reason); }
    }
    Connections {
        target: LogoutController
        function onExitApproved(): void { SessionManager.terminateSession(); }
    }
    Timer {
        interval: 300
        repeat: true
        running: LogoutController.active
        onTriggered: root.refresh()
    }
    LogoutBlockersWindow {
        id: dialog
        visible: LogoutController.active && !root.locked
        blockers: root.blockerModel()
        cancelEnabled: !LogoutController.finishing
        forceEnabled: !LogoutController.busy
        onCancelRequested: { ++root.generation; root.polling = false; LogoutController.cancel(); }
        onForceRequested: LogoutController.force()
    }
}
