//@ pragma AppId org.hics.Shell
import QtQuick
import Quickshell
import Quickshell.Io
import Hyprstack.Services
import qs.modules.session

ShellRoot {
    id: root
    property bool testLocked: false
    LogoutFlow { id: flow; locked: root.testLocked }
    Timer {
        interval: 1200; running: true; repeat: false
        onTriggered: SessionManager.logout()
    }
    function find(item,name) {
        if (item.objectName === name) return item;
        for (const child of item.children ?? []) { const found = find(child,name); if (found) return found; }
        return null;
    }
    IpcHandler {
        target: "logoutFixture"
        function cancel(): void { LogoutController.cancel(); }
        function force(): void { LogoutController.force(); }
        function active(): bool { return LogoutController.active; }
        function lock(): void { root.testLocked = true; }
        function unlock(): void { root.testLocked = false; }
        function start(): void { SessionManager.logout(); }
        function button(which: string): string {
            const item=root.find(flow.dialogWindow.contentItem, which === "cancel" ? "logoutCancel" : "logoutForce");
            if (!item) return "";
            const p=item.mapToItem(flow.dialogWindow.contentItem,item.width/2,item.height/2);
            return JSON.stringify([p.x,p.y]);
        }
        function blockers(): string { return JSON.stringify(LogoutController.blockers); }
        function state(): string { return JSON.stringify({active:LogoutController.active,ready:LogoutController.ready,
          busy:LogoutController.busy,finishing:LogoutController.finishing,error:LogoutController.error,blockers:LogoutController.blockers,
          remaining:flow.remainingWindows}); }
    }
}
