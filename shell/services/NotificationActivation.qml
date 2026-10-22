pragma Singleton
import QtQuick
import Quickshell
import Hyprstack.Services
import qs.services
import "NotificationActivation.js" as Match

Singleton {
    id: root
    property var pending: null
    property int attempts: 0
    property string requestedAddress
    property int confirmations: 0

    function entryFor(notification: var): var {
        return Match.desktopEntry(notification, ApplicationCatalogue.applications.values);
    }

    function focus(window: var): bool {
        if (!window?.lastIpcObject.mapped) return false;
        ShellState.closeDrawers();
        Overview.close(false);
        if (Hypr.usingLua && window.lastIpcObject.stableId)
            Hypr.windowAction("dock-activate", window);
        else if (Hypr.usingLua)
            Hypr.extras.message(`eval local w=hl.get_window(${JSON.stringify("address:" + window.lastIpcObject.address)}); if w then hl.dispatch(hl.dsp.focus({window=w})) end`);
        else
            Hypr.dispatch("focuswindow address:" + window.lastIpcObject.address);
        return true;
    }

    function follow(notification: var): void {
        // Copy identity: the notification/action may destroy its QML object.
        pending = {desktopEntry:notification.desktopEntry, appName:notification.appName};
        attempts = 0;
        requestedAddress = "";
        confirmations = 0;
        followAction.restart();
    }

    function open(notification: var): bool {
        pending = null;
        followAction.stop();
        const entry = entryFor(notification);
        const window = Match.bestWindow(notification, entry, Hypr.toplevels.values);
        if (window) { follow(notification); return focus(window); }
        if (!entry) return false;
        ShellState.closeDrawers();
        Overview.close(false);
        follow(notification);
        entry.execute();
        return true;
    }

    Timer {
        id: followAction
        interval: 250
        repeat: true
        onTriggered: {
            if (!root.pending) { stop(); return; }
            const entry = root.entryFor(root.pending);
            const active = Hypr.activeToplevel;
            root.attempts++;
            // The action and closing the layer surface can both change focus.
            // That is not evidence of a new user request. Allow the app to
            // choose its window, then confirm the actual compositor focus.
            const window = Match.followWindow(root.pending, entry, Hypr.toplevels.values, active);
            if (window && root.attempts >= 2) {
                const address = window.lastIpcObject.address;
                if (address === root.requestedAddress && active?.lastIpcObject.address === address)
                    root.confirmations++;
                else
                    root.confirmations = 0;
                if (root.confirmations >= 2) {
                    root.pending = null; stop(); return;
                }
                root.requestedAddress = address;
                root.focus(window);
            }
            if (root.attempts >= 12) { root.pending = null; stop(); }
        }
    }
}
