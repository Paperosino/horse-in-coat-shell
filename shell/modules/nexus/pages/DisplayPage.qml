import QtQuick
import QtQuick.Layouts
import Quickshell
import Hyprstack.Config
import Hyprstack.I18n
import qs.components
import qs.components.controls
import qs.services
import qs.utils
import qs.modules.nexus.common
import qs.modules.nexus.pages.display

PageBase {
    id: root

    property string selected: ""

    readonly property var current: Monitors.arranged.find(m => m.name === root.selected) ?? Monitors.arranged[0] ?? null
    readonly property list<real> scalePresets: [0.5, 0.75, 1, 1.25, 1.5, 1.75, 2, 2.5, 3]
    readonly property list<MenuItem> vrrItems: [
        MenuItem {
            text: Tr.trCtx("Off", "VRR")
            value: 0
        },
        MenuItem {
            text: Tr.trCtx("On", "VRR")
            value: 1
        },
        MenuItem {
            text: Tr.tr("Adaptive")
            value: 2
        }
    ]

    readonly property list<MenuItem> orientationItems: [
        MenuItem {
            text: Tr.tr("Landscape")
            value: 0
        },
        MenuItem {
            text: Tr.tr("Portrait")
            value: 1
        },
        MenuItem {
            text: Tr.tr("Landscape (flipped)")
            value: 2
        },
        MenuItem {
            text: Tr.tr("Portrait (flipped)")
            value: 3
        }
    ]

    readonly property list<real> scaleValues: {
        const scale = root.current?.scale;
        if (scale && !root.scalePresets.includes(scale))
            return [...root.scalePresets, scale].sort((a, b) => a - b);
        return root.scalePresets;
    }

    function formatRateText(rate: real): string {
        const r = Math.round(rate * 100) / 100;
        return (Number.isInteger(r) ? String(r) : r.toFixed(2)) + " " + Tr.tr("Hz");
    }

    title: Tr.tr("Display")

    ColumnLayout {
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.top: parent.top
        width: root.cappedWidth
        spacing: Tokens.spacing.extraSmall / 2

        StyledText {
            Layout.fillWidth: true
            Layout.topMargin: Tokens.padding.large
            visible: Monitors.arranged.length === 0
            text: Tr.tr("No displays detected")
            horizontalAlignment: Text.AlignHCenter
            color: Colours.palette.m3onSurfaceVariant
        }

        // Arrangement
        SectionHeader {
            first: true
            visible: Monitors.arranged.length > 0
            text: Tr.tr("Arrangement")
        }

        Arrangement {
            visible: Monitors.arranged.length > 0
            monitors: Monitors.monitors
            staged: Monitors.staged
            selected: root.current?.name ?? ""
            onSelect: name => root.selected = name
            onMoved: (name, x, y) => Monitors.stagePosition(name, x, y)
        }

        // Per-monitor settings
        SectionHeader {
            visible: root.current !== null
            text: Tr.tr("Monitor")
        }

        InfoRow {
            visible: root.current !== null
            first: true
            label: root.current?.description || root.current?.name || ""
            value: root.current?.name ?? ""
        }

        Variants {
            id: resItems

            model: root.current?.modes ?? []

            MenuItem {
                required property var modelData

                text: modelData.res.replace("x", " × ")
                value: modelData.res
            }
        }

        Variants {
            id: rateItems

            model: root.current?.modes.find(g => g.res === root.current?.resolution)?.rates ?? []

            MenuItem {
                required property var modelData

                text: root.formatRateText(modelData)
                value: modelData
            }
        }

        Variants {
            id: scaleItems

            model: root.scaleValues

            MenuItem {
                required property var modelData

                text: Strings.percentOne(modelData)
                value: modelData
            }
        }

        SelectRow {
            objectName: "displayResolution"
            visible: root.current !== null
            label: Tr.tr("Resolution")
            subtext: root.current?.focused ? Tr.tr("Focused display") : ""
            menuItems: resItems.instances
            active: resItems.instances.find(i => i.value === root.current?.resolution) ?? null
            onSelected: item => Monitors.stageResolution(root.current.name, item.value)
        }

        SelectRow {
            objectName: "displayRefreshRate"
            visible: root.current !== null
            label: Tr.tr("Refresh rate")
            menuItems: rateItems.instances
            active: {
                const cur = root.current?.rate;
                if (cur === undefined || cur === null)
                    return null;
                let best = null;
                let bestDiff = 1;
                for (const item of rateItems.instances) {
                    const diff = Math.abs(item.value - cur);
                    if (diff < bestDiff) {
                        best = item;
                        bestDiff = diff;
                    }
                }
                return best;
            }
            onSelected: item => Monitors.stageRate(root.current.name, item.value)
        }

        SelectRow {
            objectName: "displayScale"
            visible: root.current !== null
            label: Tr.tr("Scale")
            subtext: Tr.tr("Fraction of the native pixel density used for UI")
            menuItems: scaleItems.instances
            active: {
                const cur = root.current?.scale;
                if (cur === undefined || cur === null)
                    return null;
                return scaleItems.instances.find(i => Math.abs(i.value - cur) < 0.001) ?? null;
            }
            onSelected: item => Monitors.stageScale(root.current.name, item.value)
        }

        SelectRow {
            objectName: "displayOrientation"
            visible: root.current !== null
            label: Tr.tr("Orientation")
            subtext: Tr.tr("Rotation of this display")
            menuItems: root.orientationItems
            active: root.orientationItems.find(i => i.value === (root.current?.transform ?? 0)) ?? null
            onSelected: item => Monitors.stageTransform(root.current.name, item.value)
        }

        SelectRow {
            objectName: "displayVrr"
            visible: root.current !== null
            label: Tr.tr("Adaptive sync (VRR)")
            subtext: Tr.tr("Variable refresh rate mode for this display")
            menuItems: root.vrrItems
            active: root.vrrItems.find(i => i.value === (root.current?.vrr ?? 0)) ?? null
            onSelected: item => Monitors.stageVrr(root.current.name, item.value)
        }

        // Staged changes
        RowLayout {
            visible: Monitors.hasStaged
            Layout.alignment: Qt.AlignHCenter
            Layout.topMargin: Tokens.spacing.large
            spacing: Tokens.spacing.small

            TextButton {
                type: TextButton.Tonal
                isRound: true
                horizontalPadding: Tokens.padding.extraLarge
                text: Tr.tr("Revert")
                onClicked: Monitors.revert()
            }

            TextButton {
                type: TextButton.Filled
                isRound: true
                horizontalPadding: Tokens.padding.extraLarge
                text: Tr.tr("Apply")
                onClicked: Monitors.apply()
            }
        }
        SectionHeader { text: Tr.tr("Rendering & compatibility") }
        SystemSettingsSection { keys: ["xwayland.force_zero_scaling", "misc.vfr"] }

        SectionHeader { text:Tr.tr("Brightness") }
        StepperRow {
            first: true
            last: true
            label: Tr.tr("Brightness step")
            subtext: Tr.tr("Amount the brightness changes per scroll (%)")
            value: Math.round(GlobalConfig.services.brightnessIncrement * 100)
            from: 1
            to: 50
            stepSize: 1
            onMoved: v => GlobalConfig.services.brightnessIncrement = v / 100
        }

    }
}
