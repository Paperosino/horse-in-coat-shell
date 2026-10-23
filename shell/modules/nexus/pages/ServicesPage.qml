import Hyprstack.Config
import Hyprstack.I18n
import Hyprstack.Services
import QtQuick
import QtQuick.Layouts
import Quickshell
import qs.components.controls
import qs.modules.nexus.common
import qs.services

PageBase {
    id: root

    // GPU types, ordered to match config::GpuType (Auto, Nvidia, Generic, None)
    readonly property list<MenuItem> gpuItems: [
        MenuItem {
            text: Tr.trCtx("Auto", "gpu type")
        },
        MenuItem {
            text: "NVIDIA"
        },
        MenuItem {
            text: Tr.trCtx("Generic", "gpu type")
        },
        MenuItem {
            text: Tr.trCtx("None", "gpu type")
        }
    ]

    pageIcon: "build"
    title: Tr.tr("Services")

    ColumnLayout {
        width: root.cappedWidth
        anchors.horizontalCenter: parent.horizontalCenter
        spacing: Tokens.spacing.large

        SettingsCard {
            title: Tr.tr("Session")
            icon: "account_circle"

            NavRow {
                first: true
                last: true
                text: Tr.tr("User services and timers")
                icon: "settings_applications"
                subtext: Tr.tr("Manage background services for your session")
                onClicked: root.nState.openSubPage(2)
            }
        }

        SettingsCard {
            title: Tr.tr("Polling")
            icon: "monitor_heart"
            collapsible: true
            expanded: false

            StepperRow {
                first: true
                label: Tr.tr("System stats refresh")
                // TRANSLATORS: CPU and GPU are hardware abbreviations, leave them untranslated
                subtext: Tr.tr("CPU, memory and GPU update interval (seconds)")
                value: GlobalConfig.dashboard.resourceUpdateInterval / 1000
                from: 0.5
                to: 10
                stepSize: 0.5
                onMoved: v => {
                    return GlobalConfig.dashboard.resourceUpdateInterval = Math.round(v * 1000);
                }
            }

            SelectRow {
                last: true
                label: Tr.tr("GPU")
                subtext: Gpu.name ? Tr.tr("Monitoring: %1").arg(Gpu.name) : Tr.tr("Override for GPU type")
                menuOnTop: true
                menuItems: root.gpuItems
                active: root.gpuItems[GlobalConfig.services.gpuType]
                onSelected: item => {
                    return GlobalConfig.services.gpuType = root.gpuItems.indexOf(item);
                }
            }
        }
    }
}
