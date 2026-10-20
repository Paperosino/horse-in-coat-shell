pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import Hyprstack.Config
import Hyprstack.I18n
import qs.modules.nexus.common
PageBase {
    id:root
    title:Tr.tr("Panels")
    ColumnLayout {
        width:root.cappedWidth;anchors.horizontalCenter:parent.horizontalCenter;spacing:Tokens.spacing.small
        SettingsGuide { icon:"dock_to_bottom";title:Tr.tr("Everything within reach");description:Tr.tr("Arrange the statusbar, then choose how your dock and panels appear.");badges:[Tr.tr("Widgets"),Tr.tr("Dock"),Tr.tr("Panels")] }
        SectionHeader { text:Tr.tr("Statusbar & dock") }
        NavRow { first:true;text:Tr.tr("Statusbar layout");subtext:Tr.tr("Widgets and their order: left, centre and right");icon:"view_quilt";onClicked:root.nState.openSubPage(12) }
        NavRow { last:true;text:Tr.tr("Dock");subtext:Tr.tr("Position, pinned applications and app menu");icon:"dock_to_bottom";onClicked:root.nState.openSubPage(11) }
        // Additional Panel Settings Navigation
        SectionHeader {
            text: Tr.tr("Panel settings")
        }

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
