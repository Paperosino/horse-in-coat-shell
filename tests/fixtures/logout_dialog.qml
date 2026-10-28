//@ pragma AppId org.hics.Shell
import QtQuick
import Quickshell
import qs.modules.session

ShellRoot {
    id: root
    property int phase: 0
    property int cancelled: 0
    property int forced: 0
    LogoutBlockersWindow {
        id: dialog
        visible: true
        title: Quickshell.env("HICS_TEST_DIALOG_TITLE")
        blockers: [{name: "Document editor", reason: "Unsaved document"},
                   {name: "Long application name", reason: "Preparing to close"}]
        onCancelRequested: root.cancelled++
        onForceRequested: root.forced++
    }
    function find(item, name) {
        if (item.objectName === name) return item;
        for (const child of item.children ?? []) {
            const found = find(child, name);
            if (found) return found;
        }
        return null;
    }
    Timer {
        interval: 500; running: true; repeat: true
        onTriggered: {
            const list = root.find(dialog.contentItem, "logoutBlockerList");
            const cancel = root.find(dialog.contentItem, "logoutCancel");
            const force = root.find(dialog.contentItem, "logoutForce");
            if (!list || !cancel || !force || (root.phase < 2 && list.count !== 2)) {
                console.error("LOGOUT_DIALOG_FAIL: missing controls or blockers"); Qt.exit(1); return;
            }
            if (root.phase === -1) return;
            if (root.phase === 0) {
                root.phase = -1;
                root.find(dialog.contentItem, "logoutDialogContent").grabToImage(result => {
                    result.saveToFile(Quickshell.env("HICS_DIALOG_SCREENSHOT"));
                    root.phase = 1;
                });
            } else if (root.phase === 1) {
                cancel.clicked();
                if (root.cancelled !== 1 || root.forced !== 0) { Qt.exit(2); return; }
                force.clicked();
                if (root.cancelled !== 1 || root.forced !== 1) { Qt.exit(3); return; }
                dialog.blockers = [{name: "Remaining app", reason: "Still open"}];
                root.phase++;
            } else {
                if (list.count !== 1) { Qt.exit(4); return; }
                console.log("LOGOUT_DIALOG_OK"); Qt.exit(0);
            }
        }
    }
}
