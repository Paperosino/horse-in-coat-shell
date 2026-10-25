pragma ComponentBehavior: Bound
import QtQuick
import Quickshell.Services.Notifications
import qs.services
Connections {
    required property var notif
        function onClosed(reason: int): void {
            notif.notification = null;
            notif.liveActions = [];
            notif.popup = false;
            if (reason !== NotificationCloseReason.Expired || notif.isTransient)
                notif.close();
            else
                Notifs.scheduleSave();
        }

        function onSummaryChanged(): void {
            notif.summary = notif.notification.summary;
            notif.updated();
        }

        function onBodyChanged(): void {
            notif.body = notif.notification.body;
            notif.updated();
        }

        function onAppIconChanged(): void {
            notif.appIcon = notif.notification.appIcon;
        }

        function onAppNameChanged(): void {
            notif.appName = notif.notification.appName;
        }

        function onImageChanged(): void {
            notif.image = notif.notification.image;
            notif.maybeTriggerDummyImageLoader();
        }

        function onExpireTimeoutChanged(): void {
            notif.expireTimeout = notif.notification.expireTimeout;
        }

        function onUrgencyChanged(): void {
            notif.urgency = notif.notification.urgency;
        }

        function onResidentChanged(): void {
            notif.resident = notif.notification.resident;
        }

        function onHasActionIconsChanged(): void {
            notif.hasActionIcons = notif.notification.hasActionIcons;
        }

        function onActionsChanged(): void {
            // qmllint disable unresolved-type
            notif.liveActions = notif.notification.actions.map(a => ({
                        // qmllint enable unresolved-type
                        identifier: a.identifier,
                        text: a.text,
                        invoke: () => a.invoke()
                    }));
        }

        function onHintsChanged(): void {
            notif.hints = notif.notification.hints;
            notif.maybeTriggerDummyImageLoader();
        }

        function onTransientChanged(): void {
            notif.isTransient = notif.notification.transient;
            Notifs.scheduleSave();
        }

        target: notif.notification
    }

