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

        SettingsCard {
            title: Tr.tr("Dock animations")
            description: Tr.tr("An elastic wave lifts neighbouring icons inside one liquid surface. Window transitions land on their application icon.")
            icon: "animation"
            badge: "Expressive"
            DockMotionPreview {Layout.fillWidth:true}
            ToggleRow {text:Tr.tr("Liquid dock");subtext:Tr.tr("Lift icons and stretch the shared membrane towards the pointer");checked:DockConf.animations;onToggled:DockConf.setMotion("animations",checked)}
            ToggleRow {text:Tr.tr("Minimize and restore windows");subtext:Tr.tr("Spring window transitions and icon absorption in stacking mode");checked:DockConf.windowAnimations;onToggled:DockConf.setMotion("windowAnimations",checked)}
            StepperRow {label:Tr.tr("Icon lift");subtext:Tr.tr("Height of the wave (dp)");value:DockConf.lift;from:8;to:40;stepSize:2;onMoved:v=>DockConf.setMotion("lift",v)}
            StepperRow {label:Tr.tr("Magnification");subtext:Tr.tr("Maximum icon scale (%)");value:Math.round(DockConf.magnification*100);from:100;to:150;stepSize:5;onMoved:v=>DockConf.setMotion("magnification",v/100)}
            StepperRow {label:Tr.tr("Wave spread");subtext:Tr.tr("How far neighbouring icons follow the pointer (dp)");value:DockConf.spread;from:36;to:120;stepSize:4;onMoved:v=>DockConf.setMotion("spread",v)}
            StepperRow {label:Tr.tr("Spring damping");subtext:Tr.tr("Higher values make the landing calmer (%)");value:Math.round(DockConf.damping*100);from:55;to:100;stepSize:5;onMoved:v=>DockConf.setMotion("damping",v/100)}
            StepperRow {label:Tr.tr("Window transition duration");subtext:Tr.tr("Minimize and restore timing (ms)");value:DockConf.animationDuration;from:240;to:700;stepSize:20;onMoved:v=>DockConf.setMotion("animationDuration",v)}
            RowButton {text:Tr.tr("Reset dock animations");icon:"restart_alt";onClicked:DockConf.resetMotion()}
            InfoRow {label:Tr.tr("Accessibility");value:Tr.tr("Reduce motion disables the wave and window travel")}
        }

        InfoRow {
            last: true
            label: Tr.tr("Pinned apps")
            value: Tr.trN("%n pinned app", "%n pinned apps", Taskbar.pinned.length)
        }
    }
}
