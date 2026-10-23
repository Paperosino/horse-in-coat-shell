pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import Quickshell
import Hyprstack.Config
import Hyprstack.I18n
import qs.components
import qs.components.controls
import qs.services
import qs.modules.nexus.common

PageBase {
    id: root
    pageIcon: "battery_charging_full"

    title: Tr.tr("Power & lock")

    ColumnLayout {
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.top: parent.top
        width: root.cappedWidth
        spacing: Tokens.spacing.large

        PowerProfilesSection {}

        // Lock
        SettingsCard {
            title: Tr.tr("Lock screen")
            icon: "lock"

            IdleTimeoutChooser {
                idleAction: "lock"
                title: Tr.tr("Lock screen after")
                subtext: Tr.tr("Lock the session after a period of inactivity")
                presetMinutes: [1, 2, 3, 5, 10, 15]
            }

            // Screen
        }
        SettingsCard {
            title: Tr.tr("Screen")
            icon: "monitor"

            IdleTimeoutChooser {
                idleAction: "dpms off"
                title: Tr.tr("Turn off screen after")
                subtext: Tr.tr("Put displays to sleep; they wake on input")
                presetMinutes: [1, 2, 3, 5, 10, 15, 30]
            }

            // Suspend
        }
        SettingsCard {
            title: Tr.tr("Power")
            icon: "battery_charging_full"

            IdleTimeoutChooser {
                idleAction: ["suspend"]
                title: Tr.tr("Suspend after")
                subtext: Tr.tr("System sleeps after a period of inactivity")
                presetMinutes: [5, 10, 15, 30, 45, 60, 120]
            }

            // Idle behaviour
        }
        SettingsCard {
            title: Tr.tr("Idle behaviour")
            icon: "bedtime"

            ToggleRow {
                first: true
                text: Tr.tr("Lock before suspending")
                checked: GlobalConfig.general.idle.lockBeforeSleep
                onToggled: GlobalConfig.general.idle.lockBeforeSleep = checked
            }

            ToggleRow {
                text: Tr.tr("Inhibit idle while media is playing")
                subtext: Tr.tr("Playback keeps the session awake")
                checked: GlobalConfig.general.idle.inhibitWhenAudio
                onToggled: GlobalConfig.general.idle.inhibitWhenAudio = checked
            }

            ToggleRow {
                last: true
                text: Tr.tr("Inhibit idle while charging")
                subtext: Tr.tr("The system stays awake while plugged in")
                checked: GlobalConfig.general.idle.inhibitWhenCharging
                onToggled: GlobalConfig.general.idle.inhibitWhenCharging = checked
            }
        }
    }

    component IdleTimeoutChooser: ColumnLayout {
        id: chooser

        required property var idleAction
        required property string title
        required property string subtext
        required property list<int> presetMinutes
        property int maxMinutes: 720

        spacing: 0
        Layout.fillWidth: true

        readonly property var entry: {
            const want = chooser.idleAction;
            for (const node of GlobalConfig.general.idle.timeouts.values) {
                const action = node.idleAction;
                if (typeof want === "string") {
                    if (action === want)
                        return node;
                } else {
                    // A stored QStringList can surface as an array-like
                    // object instead of a JS array — normalise before use.
                    const list = Array.isArray(action) ? action : Array.from(action ?? []);
                    if (list.length > 0 && list[0] === want[0])
                        return node;
                }
            }
            return null;
        }

        readonly property list<MenuItem> items: [...presetItems.instances, customItem, neverItem]

        readonly property var activeItem: {
            if (!chooser.entry || !chooser.entry.enabled)
                return chooser.entry ? neverItem : null;
            const minutes = chooser.entry.timeout / 60;
            return presetItems.instances.find(i => i.value === minutes) ?? customItem;
        }

        function formatMinutes(m: int): string {
            if (m < 60)
                return Tr.trN("%n minute", "%n minutes", m);
            if (m % 60 === 0)
                return Tr.trN("%n hour", "%n hours", m / 60);
            return Tr.trN("%n min", "%n mins", m);
        }

        Variants {
            id: presetItems

            model: chooser.presetMinutes

            MenuItem {
                required property var modelData

                text: chooser.formatMinutes(modelData)
                value: modelData
            }
        }

        MenuItem {
            id: customItem

            text: Tr.tr("Custom…")
            value: "custom"
        }

        MenuItem {
            id: neverItem

            text: Tr.tr("Never")
            value: "never"
        }

        SelectRow {
            first: true
            label: chooser.title
            subtext: chooser.entry ? chooser.subtext : Tr.tr("This idle action is not configured")
            enabled: chooser.entry !== null
            menuItems: chooser.items
            active: chooser.activeItem
            onSelected: item => {
                if (!chooser.entry)
                    return;
                if (item.value === "never") {
                    chooser.entry.enabled = false;
                } else if (item.value === "custom") {
                    chooser.entry.enabled = true;
                } else {
                    chooser.entry.enabled = true;
                    chooser.entry.timeout = item.value * 60;
                }
            }
        }

        StepperRow {
            last: true
            visible: chooser.activeItem === customItem && chooser.entry !== null
            label: Tr.tr("Custom delay")
            subtext: Tr.tr("Minutes of inactivity")
            value: (chooser.entry?.timeout ?? 0) / 60
            from: 1
            to: chooser.maxMinutes
            stepSize: 1
            onMoved: v => {
                if (chooser.entry)
                    chooser.entry.timeout = Math.round(v * 60);
            }
        }
    }
}
