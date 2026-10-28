//@ pragma AppId org.hics.Shell
import QtQuick
import Quickshell
import qs.modules.session

ShellRoot {
    id: root
    property int phase: 0
    property int cancelled: 0
    property int forced: 0
    readonly property bool pointerTest: Quickshell.env("HICS_TEST_POINTER") === "1"
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
            if (!list || !cancel || !force || (root.phase < 3 && list.count !== 2)) {
                console.error("LOGOUT_DIALOG_FAIL: missing controls or blockers"); Qt.exit(1); return;
            }
            if (root.phase === -1) return;
            if (root.phase === 0) {
                root.phase = -1;
                root.find(dialog.contentItem, "logoutDialogContent").grabToImage(result => {
                    result.saveToFile(Quickshell.env("HICS_DIALOG_SCREENSHOT"));
                    if (root.pointerTest) {
                        const c = cancel.mapToItem(dialog.contentItem, cancel.width / 2, cancel.height / 2);
                        const f = force.mapToItem(dialog.contentItem, force.width / 2, force.height / 2);
                        console.log("LOGOUT_BUTTONS", JSON.stringify({cancel: [c.x,c.y], force: [f.x,f.y]}));
                    }
                    root.phase = 1;
                });
            } else if (root.phase === 1) {
                if (!root.pointerTest) cancel.clicked();
                if (root.forced !== 0 || root.cancelled > 1) { Qt.exit(2); return; }
                if (root.cancelled === 1) { root.phase = 2; console.log("LOGOUT_READY_FORCE"); }
            } else if (root.phase === 2) {
                if (!root.pointerTest) force.clicked();
                if (root.cancelled !== 1 || root.forced > 1) { Qt.exit(3); return; }
                if (root.forced === 1) {
                    dialog.blockers = [{name: "Remaining app", reason: "Still open"}];
                    root.phase = 3;
                }
            } else {
                if (list.count !== 1) { Qt.exit(4); return; }
                console.log("LOGOUT_DIALOG_OK"); Qt.exit(0);
            }
        }
    }
}
