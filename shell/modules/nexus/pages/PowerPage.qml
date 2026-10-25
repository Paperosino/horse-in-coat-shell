pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import Quickshell
import Hyprstack.Config
import Hyprstack.Services
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
        SettingsCard {
            title:Tr.tr("Temporary wake lock");icon:"coffee"
            RowButton {text:Tr.tr("Stay awake for 30 minutes");icon:"schedule";onClicked:DesktopJobs.request("comfort.awake",{minutes:30})}
            RowButton {visible:Comfort.awake;text:Tr.tr("End temporary wake lock");icon:"close";onClicked:DesktopJobs.request("comfort.awake",{minutes:0})}
            NavRow {text:Tr.tr("Focus & breaks");subtext:Tr.tr("Work intervals, breaks and more wake-lock durations");onClicked:root.nState.openPage("focus")}
        }
        SettingsCard {
            title: Tr.tr("Laptop & docking")
            icon: "laptop_mac"
            ToggleRow { first:true;last:true;text:Tr.tr("Stay awake with the lid closed when an external display is connected");checked:GlobalConfig.general.idle.keepAwakeDocked;onToggled:GlobalConfig.general.idle.keepAwakeDocked=checked }
            InfoRow {first:true;last:true;label:Tr.tr("Lid handling");value:DesktopConveniences.dockInhibited?Tr.tr("External display: lid sleep is inhibited"):Tr.tr("System lid policy is active")}
            FeatureError {error:DesktopConveniences.error}
        }

        // Lock
        SettingsCard {
            title: Tr.tr("Lock screen")
            icon: "lock"

            IdleTimeoutChooser {
                idleAction: "lock"
                title: Tr.tr("Lock screen after")
                subtext: Tr.tr("Lock the session after a period of inactivity")

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

        InfoRow {first:true;last:true;label:chooser.title;value:chooser.subtext}
        ToggleRow {first:true;last:true;text:Tr.tr("Enabled");checked:chooser.entry?.enabled??false;enabled:chooser.entry!==null;onToggled:if(chooser.entry)chooser.entry.enabled=checked}
        StepperRow {
            visible: chooser.entry !== null
            label: Tr.tr("On battery (minutes)")
            subtext: Tr.tr("0 disables this action")
            value: Math.round((chooser.entry?.batteryTimeout >= 0 ? chooser.entry.batteryTimeout : chooser.entry?.timeout ?? 0)/60)
            from:0;to:720;stepSize:1
            onMoved: v => {if(chooser.entry){chooser.entry.enabled=true;chooser.entry.batteryTimeout=Math.round(v*60);}}
        }
        StepperRow {
            last:true
            visible: chooser.entry !== null
            label: Tr.tr("Plugged in (minutes)")
            subtext: Tr.tr("0 disables this action")
            value: Math.round((chooser.entry?.acTimeout >= 0 ? chooser.entry.acTimeout : chooser.entry?.timeout ?? 0)/60)
            from:0;to:720;stepSize:1
            onMoved: v => {if(chooser.entry){chooser.entry.enabled=true;chooser.entry.acTimeout=Math.round(v*60);}}
        }
    }
}
