pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import Hyprstack.Config
import Hyprstack.I18n
import qs.modules.nexus.common

PageBase {
    id: root
    pageIcon: "dashboard"
    title: Tr.tr("Panels")
    ColumnLayout {
        width: root.cappedWidth
        anchors.horizontalCenter: parent.horizontalCenter
        spacing: Tokens.spacing.small
        SettingsGuide {
            icon: "dock_to_bottom"
            title: Tr.tr("Everything within reach")
            description: Tr.tr("Widgets and their order: left, centre and right")
            badges: [Tr.tr("Widgets"), Tr.tr("Panels")]
        }
        SettingsCard {
            title: Tr.tr("Statusbar layout")
            icon: "dashboard"

            NavRow {
                first: true
                last: true
                text: Tr.tr("Statusbar layout")
                subtext: Tr.tr("Widgets and their order: left, centre and right")
                icon: "view_quilt"
                onClicked: root.nState.openSubPage(12)
            }

            // Additional Panel Settings Navigation
        }
        SettingsCard {
            title: Tr.tr("Panel settings")
            icon: "dashboard"

            NavRow {
                first: true
                icon: "dashboard"
                text: Tr.tr("Dashboard")
                subtext: Config.dashboard.enabled ? Tr.trCtx("Enabled", "panel status") : Tr.trCtx("Disabled", "panel status")
                onClicked: root.nState.openSubPage(1)
            }

            NavRow {
                icon: "dock_to_bottom"
                text: Tr.tr("Taskbar options")
                subtext: Config.bar.persistent ? Tr.tr("Always visible") : Config.bar.showOnHover ? Tr.tr("Reveal on hover") : Tr.tr("Reveal on drag")
                onClicked: root.nState.openSubPage(2)
            }

            NavRow {
                icon: "apps"
                text: Tr.tr("Launcher")
                subtext: Config.launcher.enabled ? Tr.trCtx("Enabled", "panel status") : Tr.trCtx("Disabled", "panel status")
                onClicked: root.nState.openSubPage(3)
            }

            NavRow {
                icon: "dock_to_right"
                text: Tr.tr("Sidebar")
                subtext: Config.sidebar.enabled ? Tr.trCtx("Enabled", "panel status") : Tr.trCtx("Disabled", "panel status")
                onClicked: root.nState.openSubPage(4)
            }

            NavRow {
                last: true
                icon: "construction"
                text: Tr.tr("Utilities")
                subtext: Config.utilities.enabled ? Tr.trCtx("Enabled", "panel status") : Tr.trCtx("Disabled", "panel status")
                onClicked: root.nState.openSubPage(5)
            }
        }
    }
}
