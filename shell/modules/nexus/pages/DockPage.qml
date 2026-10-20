import QtQuick
import QtQuick.Layouts
import Hyprstack.Config
import Hyprstack.I18n
import qs.components.controls
import qs.services
import qs.modules.nexus.common

PageBase {
    id: root

    title: Tr.tr("Dock")

    readonly property list<MenuItem> positionItems: [
        MenuItem { text: Tr.tr("Bottom"); icon: "arrow_downward"; value: "bottom" },
        MenuItem { text: Tr.tr("Top"); icon: "arrow_upward"; value: "top" },
        MenuItem { text: Tr.tr("Left"); icon: "arrow_back"; value: "left" },
        MenuItem { text: Tr.tr("Right"); icon: "arrow_forward"; value: "right" }
    ]

    readonly property list<MenuItem> buttonPositionItems: [
        MenuItem { text: Tr.tr("Before applications"); value: "start" },
        MenuItem { text: Tr.tr("After applications"); value: "end" }
    ]

    ColumnLayout {
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.top: parent.top
        width: root.cappedWidth
        spacing: Tokens.spacing.extraSmall / 2

        SectionHeader {
            first: true
            text: Tr.tr("Behaviour")
        }

        ToggleRow {
            first: true
            text: Tr.tr("Enable dock")
            subtext: Tr.tr("Pinned apps, app list")
            checked: DockConf.enabled
            onToggled: DockConf.setEnabled(checked)
        }

        SelectRow {
            label: Tr.tr("Position")
            menuItems: root.positionItems
            active: root.positionItems.find(item => item.value === DockConf.position)
            onSelected: item => DockConf.setPosition(item.value)
        }

        SelectRow {
            label: Tr.tr("App menu button")
            menuItems: root.buttonPositionItems
            active: DockConf.menuButtonPosition === "start" ? root.buttonPositionItems[0] : root.buttonPositionItems[1]
            onSelected: item => DockConf.setMenuButtonPosition(item.value)
        }

        StepperRow {
            label: Tr.tr("Icon size")
            subtext: Tr.tr("Size of dock icons (px)")
            value: DockConf.iconSize
            from: 32
            to: 64
            stepSize: 4
            onMoved: v => DockConf.setIconSize(v)
        }

        InfoRow {
            last: true
            label: Tr.tr("Pinned apps")
            value: Tr.trN("%n pinned app", "%n pinned apps", Taskbar.pinned.length)
        }
    }
}
