pragma Singleton
import QtQuick
import Quickshell
import Hyprstack.Config
Singleton {
    id: root
    property alias active: lease.active
    property alias screenName: lease.screenName
    property alias endsAt: lease.endsAt
    property int durationMinutes: GlobalConfig.utilities.presentation.durationMinutes
    property bool hideNotifications: GlobalConfig.utilities.presentation.hideNotifications
    property bool hidePrivateContent: GlobalConfig.utilities.presentation.hidePrivateContent
    onDurationMinutesChanged: GlobalConfig.utilities.presentation.durationMinutes = durationMinutes
    onHideNotificationsChanged: GlobalConfig.utilities.presentation.hideNotifications = hideNotifications
    onHidePrivateContentChanged: GlobalConfig.utilities.presentation.hidePrivateContent = hidePrivateContent
    function privateOn(screen): bool {
        return active && hidePrivateContent && screen?.name === screenName;
    }
    function begin(screen: string): void {
        if (!Quickshell.screens.some(output => output.name === screen)) return;
        screenName = screen;
        endsAt = Date.now() + Math.max(1, Math.min(480, durationMinutes)) * 60000;
        active = true;
    }
    function end(): void { active = false; endsAt = 0; }
    PersistentProperties {
        id: lease
        reloadableId: "presentationLease"
        property bool active: false
        property string screenName: ""
        property double endsAt: 0
    }
    Timer {
        interval: 1000; repeat: true; running: root.active
        onTriggered: {
            if (Date.now() >= root.endsAt || !Quickshell.screens.some(screen => screen.name === root.screenName)) root.end();
        }
    }
}
