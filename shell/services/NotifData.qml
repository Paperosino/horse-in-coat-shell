pragma ComponentBehavior: Bound

import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Services.Notifications
import Hyprstack
import Hyprstack.Config
import Hyprstack.I18n
import qs.services
import qs.utils
import "NotificationStore.js" as Store

QtObject {
    id: notif

    property bool expiryPaused:false
    function pauseExpiry():void {expiryPaused=true;popupDeadline=0;Notifs.armExpiration();}
    function resumeExpiry():void {expiryPaused=false;Notifs.expirationChanged(notif);}
    property real popupDeadline:0
    property bool popup
    property bool closed
    property bool retiring: false
    property bool read
    property bool isTransient
    property bool fromPreviousGeneration
    property string historyId: "notification-" + Date.now() + "-" + Math.random().toString(36).slice(2)
    property var locks: new Set()

    property date time: new Date()
    property int ageMins: 0
    readonly property string timeStr: {
        if (ageMins < 1)
            return Tr.tr("now");

        const h = Math.floor(ageMins / 60);
        const d = Math.floor(h / 24);

        if (d > 0)
            return Tr.trCtx("%1d", "abbreviated notification age, days").arg(d);
        if (h > 0)
            return Tr.trCtx("%1h", "abbreviated notification age, hours").arg(h);
        return Tr.trCtx("%1m", "abbreviated notification age, minutes").arg(ageMins);
    }

    property Notification notification
    property string notificationId
    property string summary
    property string body
    property string appIcon
    property string appName
    property string image
    property bool screenshot
    property string screenshotPath
    property string desktopEntry
    property var hints // Hints are not persisted across restarts
    property real expireTimeout: GlobalConfig.notifs.defaultExpireTimeout
    property int urgency: NotificationUrgency.Normal
    property bool resident
    property bool hasActionIcons
    property list<var> liveActions
    readonly property list<var> actions: {
        const live = liveActions.filter(a => a.identifier !== "default");
        if (!screenshot)
            return live;
        // Screenshot actions belong to the shell, so they work even after the
        // sending process or notification server has restarted.
        return [
            {identifier: "open", text: Tr.tr("Open"), invoke: () => notif.imageAction("open")},
            {identifier: "copy", text: Tr.tr("Copy"), invoke: () => notif.imageAction("copy")},
            {identifier: "save", text: Tr.tr("Save"), invoke: () => notif.imageAction("save")},
            {identifier: "reveal", text: Tr.tr("Show in folder"), invoke: () => notif.imageAction("reveal")}
        ];
    }

    onReadChanged: Notifs.scheduleSave()
    onImageChanged: Notifs.scheduleSave()
    onScreenshotPathChanged: Notifs.scheduleSave()
    onClosedChanged: Notifs.scheduleSave()
    onExpireTimeoutChanged: Notifs.expirationChanged(notif)
    onHasFullscreenChanged: if(popup)Notifs.expirationChanged(notif)
    onPopupChanged: {
        Notifs.expirationChanged(notif)
        if (!popup && isTransient && notification)
            notification.expire();
    }

    function imageAction(action: string): void {
        read = true;
        Notifs.imageAction(notif, action);
    }

    function restoreHistory(properties: var): void {
        time = properties.time;
        read = properties.read;
        historyId = properties.historyId;
        if (properties.image)
            image = properties.image;
        if (properties.screenshotPath)
            screenshotPath = properties.screenshotPath;
        screenshot = properties.screenshot || screenshot;
        updateTimeStr();
    }

    function activate(): bool {
        read = true;
        popup = false;
        if (screenshot) {
            imageAction("open");
            return true;
        }
        const action = liveActions.find(a => a.identifier === "default");
        if (action) {
            ShellState.closeDrawers();
            Overview.close(false);
            NotificationActivation.follow(notif);
            action.invoke();
            return true;
        }
        return NotificationActivation.open(notif);
    }

    function updated(): void {
        time = new Date();
        updateTimeStr();
        read = ShellState.anySidebarOpen();
        popup = Notifs.shouldShowPopup();
        Notifs.touch(notif);
    }

    readonly property bool hasFullscreen: {
        const monitor = Hypr.focusedMonitor;
        const specialName = monitor?.lastIpcObject.specialWorkspace?.name;
        if (specialName) {
            const specialWs = Hypr.workspaces.values.find(ws => ws.name === specialName);
            return specialWs?.toplevels.values.some(t => t.lastIpcObject.fullscreen > 1) ?? false;
        }
        return monitor?.activeWorkspace?.toplevels.values.some(t => t.lastIpcObject.fullscreen > 1) ?? false;
    }

    function updateTimeStr(): void {
        const diff = Date.now() - time.getTime();
        ageMins = Math.max(0, Math.floor(diff / 60000));
    }

    function maybeTriggerDummyImageLoader(): void {
        if (!notification)
            return;
        const path = Store.imagePath(notification);
        screenshot = Store.isScreenshot(notification, path);
        if (screenshot && path)
            screenshotPath = path;
        const source = path || image;
        if (source && !source.startsWith("image://icon/") && !source.startsWith(Paths.notifimagecache + "/")) {
            image = source;
            Notifs.cacheImage(notif, source, screenshot);
        }
    }

    function lock(item: Item): void {
        locks.add(item);
    }

    function unlock(item: Item): void {
        locks.delete(item);
        if (closed)
            close();
    }

    function close(): void {
        if (retiring)
            return;
        closed = true;
        popup = false;
        if (notification) {
            const remote = notification;
            notification = null;
            remote.dismiss();
        }
        if (locks.size === 0) {
            retiring = true;
            if (Notifs.list.includes(this))
                Notifs.list = Notifs.list.filter(n => n !== this);
            destroy();
        }
    }

    Component.onCompleted: {
        updateTimeStr();
        if (!notification)
            return;

        notificationId = notification.id;
        summary = notification.summary;
        body = notification.body;
        appIcon = notification.appIcon;
        appName = notification.appName;
        desktopEntry = notification.desktopEntry;
        isTransient = notification.transient;
        image = notification.image;
        maybeTriggerDummyImageLoader();
        expireTimeout = notification.expireTimeout;
        hints = notification.hints;
        urgency = notification.urgency;
        resident = notification.resident;
        hasActionIcons = notification.hasActionIcons;
        // qmllint disable unresolved-type
        liveActions = notification.actions.map(a => ({
                    // qmllint enable unresolved-type
                    identifier: a.identifier,
                    text: a.text,
                    invoke: () => a.invoke()
                }));
    }
}
