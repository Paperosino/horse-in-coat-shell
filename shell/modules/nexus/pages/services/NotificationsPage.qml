import QtQuick
import QtQuick.Layouts
import Hyprstack.Config
import Hyprstack.I18n
import Hyprstack.Services
import qs.services
import qs.components.controls
import qs.modules.nexus.common

PageBase {
    id: root
    pageIcon: "notifications"

    // Notification fullscreen visibility, ordered to match config::NotifsFullscreen (On, Off)
    readonly property list<MenuItem> notifFullscreenItems: [
        MenuItem {
            text: Tr.trCtx("On", "show notifications over fullscreen apps")
            icon: "notifications"
        },
        MenuItem {
            text: Tr.trCtx("Off", "show notifications over fullscreen apps")
            icon: "notifications_off"
        }
    ]

    // Toast fullscreen visibility, mapped to GlobalConfig.utilities.toasts.fullscreen
    readonly property list<MenuItem> toastFullscreenItems: [
        MenuItem {
            text: Tr.trCtx("Off", "show toasts over fullscreen apps")
            icon: "notifications_off"
        },
        MenuItem {
            text: Tr.trCtx("Important", "show toasts over fullscreen apps: important ones only")
            icon: "priority_high"
        },
        MenuItem {
            text: Tr.trCtx("On", "show toasts over fullscreen apps")
            icon: "notifications"
        }
    ]
    readonly property list<string> toastFullscreenValues: ["off", "important", "all"]

    title: Tr.tr("Notifications")

    ColumnLayout {
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.top: parent.top
        width: root.cappedWidth
        spacing: Tokens.spacing.large

        SettingsCard {
            title: Tr.tr("Do not disturb")
            icon: "tune"

            ToggleRow {
                first: true
                text: Tr.tr("Do not disturb")
                checked: Notifs.dnd
                onToggled: Notifs.dnd = checked
            }
            RowButton {
                text: Tr.tr("Pause popups for 30 minutes")
                icon: "snooze"
                onClicked: NotificationPolicy.pauseFor(30)
            }
            RowButton {
                text: Tr.tr("Pause popups for 1 hour")
                icon: "snooze"
                onClicked: NotificationPolicy.pauseFor(60)
            }
            RowButton {
                last: true
                visible: NotificationPolicy.paused
                text: Tr.tr("Resume popups")
                icon: "notifications_active"
                subtext: new Date(NotificationPolicy.pausedUntil * 1000).toLocaleString()
                onClicked: NotificationPolicy.resume()
            }
        }
        SettingsCard {
            title: Tr.tr("Application rules")
            icon: "tune"

            Repeater {
                model: NotificationPolicy.applications
                SelectRow {
                    id: appRule
                    required property var modelData
                    first: true
                    last: true
                    label: modelData.name || modelData.id
                    subtext: modelData.id
                    menuItems: [allRule, silentRule, blockedRule]
                    active: modelData.mode === "blocked" ? blockedRule : modelData.mode === "silent" ? silentRule : allRule
                    onSelected: item => NotificationPolicy.setRule(modelData.id, item.value)
                    MenuItem {
                        id: allRule
                        text: Tr.tr("Popups and history")
                        value: "all"
                    }
                    MenuItem {
                        id: silentRule
                        text: Tr.tr("History only")
                        value: "silent"
                    }
                    MenuItem {
                        id: blockedRule
                        text: Tr.tr("Block new notifications")
                        value: "blocked"
                    }
                }
            }
            FeatureError {
                error: NotificationPolicy.error
            }

            // Notifications
        }
        SettingsCard {
            title: Tr.tr("Notifications")
            icon: "notifications"

            SelectRow {
                first: true
                label: Tr.tr("Show in fullscreen")
                subtext: Tr.tr("Whether notifications appear over fullscreen apps")
                menuItems: root.notifFullscreenItems
                active: root.notifFullscreenItems[GlobalConfig.notifs.fullscreen]
                onSelected: item => GlobalConfig.notifs.fullscreen = root.notifFullscreenItems.indexOf(item)
            }

            ToggleRow {
                text: Tr.tr("Open application on click")
                subtext: Tr.tr("Use the application's notification action or switch to its existing window")
                checked: GlobalConfig.notifs.actionOnClick
                onToggled: GlobalConfig.notifs.actionOnClick = checked
            }

            ToggleRow {
                text: Tr.tr("Expire automatically")
                subtext: Tr.tr("Dismiss notifications after their timeout")
                checked: GlobalConfig.notifs.expire
                onToggled: GlobalConfig.notifs.expire = checked
            }

            ToggleRow {
                text: Tr.tr("Open expanded")
                subtext: Tr.tr("Show notifications expanded by default")
                checked: GlobalConfig.notifs.openExpanded
                onToggled: GlobalConfig.notifs.openExpanded = checked
            }

            StepperRow {
                label: Tr.tr("Default timeout")
                // TRANSLATORS: ms is the millisecond unit, leave it untranslated
                subtext: Tr.tr("Time before a notification dismisses (ms)")
                value: GlobalConfig.notifs.defaultExpireTimeout
                from: 1000
                to: 60000
                stepSize: 500
                onMoved: v => GlobalConfig.notifs.defaultExpireTimeout = Math.round(v)
            }

            StepperRow {
                last: true
                label: Tr.tr("Group preview count")
                subtext: Tr.tr("Notifications shown per group before collapsing")
                value: GlobalConfig.notifs.groupPreviewNum
                from: 1
                to: 10
                stepSize: 1
                onMoved: v => GlobalConfig.notifs.groupPreviewNum = Math.round(v)
            }

            // Toasts
        }
        SettingsCard {
            title: Tr.tr("Toasts")
            icon: "tune"

            SelectRow {
                first: true
                label: Tr.tr("Show in fullscreen")
                subtext: Tr.tr("Whether toasts appear over fullscreen apps")
                menuItems: root.toastFullscreenItems
                active: root.toastFullscreenItems[Math.max(0, root.toastFullscreenValues.indexOf(GlobalConfig.utilities.toasts.fullscreen))]
                onSelected: item => GlobalConfig.utilities.toasts.fullscreen = root.toastFullscreenValues[root.toastFullscreenItems.indexOf(item)]
            }

            StepperRow {
                last: true
                label: Tr.tr("Visible toasts")
                subtext: Tr.tr("Maximum number of toasts shown at once")
                value: GlobalConfig.utilities.maxToasts
                from: 1
                to: 10
                stepSize: 1
                onMoved: v => GlobalConfig.utilities.maxToasts = Math.round(v)
            }

            // Toast events
        }
        SettingsCard {
            title: Tr.tr("Toast events")
            icon: "tune"

            ToggleRow {
                first: true
                text: Tr.tr("Charging changes")
                checked: GlobalConfig.utilities.toasts.chargingChanged
                onToggled: GlobalConfig.utilities.toasts.chargingChanged = checked
            }

            ToggleRow {
                text: Tr.tr("Game mode changes")
                checked: GlobalConfig.utilities.toasts.gameModeChanged
                onToggled: GlobalConfig.utilities.toasts.gameModeChanged = checked
            }

            ToggleRow {
                text: Tr.tr("Do not disturb changes")
                checked: GlobalConfig.utilities.toasts.dndChanged
                onToggled: GlobalConfig.utilities.toasts.dndChanged = checked
            }

            ToggleRow {
                text: Tr.tr("Audio output changes")
                checked: GlobalConfig.utilities.toasts.audioOutputChanged
                onToggled: GlobalConfig.utilities.toasts.audioOutputChanged = checked
            }

            ToggleRow {
                text: Tr.tr("Audio input changes")
                checked: GlobalConfig.utilities.toasts.audioInputChanged
                onToggled: GlobalConfig.utilities.toasts.audioInputChanged = checked
            }

            ToggleRow {
                text: Tr.tr("Caps lock changes")
                checked: GlobalConfig.utilities.toasts.capsLockChanged
                onToggled: GlobalConfig.utilities.toasts.capsLockChanged = checked
            }

            ToggleRow {
                text: Tr.tr("Num lock changes")
                checked: GlobalConfig.utilities.toasts.numLockChanged
                onToggled: GlobalConfig.utilities.toasts.numLockChanged = checked
            }

            ToggleRow {
                text: Tr.tr("Keyboard layout changes")
                checked: GlobalConfig.utilities.toasts.kbLayoutChanged
                onToggled: GlobalConfig.utilities.toasts.kbLayoutChanged = checked
            }

            ToggleRow {
                text: Tr.tr("VPN changes")
                checked: GlobalConfig.utilities.toasts.vpnChanged
                onToggled: GlobalConfig.utilities.toasts.vpnChanged = checked
            }

            ToggleRow {
                last: true
                text: Tr.tr("Now playing")
                checked: GlobalConfig.utilities.toasts.nowPlaying
                onToggled: GlobalConfig.utilities.toasts.nowPlaying = checked
            }
        }
    }
}
