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
    pageIcon: "monitor"

    property string selected: ""
    property string deletingProfile: ""

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
            text: Tr.tr("Fullscreen only")
            value: 2
        },
        MenuItem { text: Tr.tr("Fullscreen games only"); value: 3 }
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

    Component.onCompleted:DisplayProfiles.refresh()

    title: Tr.tr("Display")

    ColumnLayout {
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.top: parent.top
        width: root.cappedWidth
        spacing: Tokens.spacing.large

        StyledText {
            Layout.fillWidth: true
            Layout.topMargin: Tokens.padding.large
            visible: Monitors.arranged.length === 0
            text: Tr.tr("No displays detected")
            horizontalAlignment: Text.AlignHCenter
            color: Colours.palette.m3onSurfaceVariant
        }

        SettingsCard {
            title:Tr.tr("Display profiles")
            description:Tr.tr("Save a layout for home, a dock or your laptop. Matching screens restore their resolution, refresh rate, scale and positions automatically.")
            icon:"devices"
            FeatureError {error:DisplayProfiles.error}
            StyledText {Layout.fillWidth:true;visible:!!DisplayProfiles.notice;text:Tr.tr(DisplayProfiles.notice);textFormat:Text.PlainText;wrapMode:Text.WordWrap;color:Colours.palette.m3onSurfaceVariant}
            ToggleRow {text:Tr.tr("Recognize connected display setups");subtext:Tr.tr("Automatic changes also require confirmation and revert if the timer expires.");checked:DisplayProfiles.settings.autoApply??true;onToggled:DisplayProfiles.configure({autoApply:checked})}
            GridLayout {
                Layout.fillWidth:true;columns:width>520*Tokens.scale?2:1
                StyledTextField {id:profileName;Layout.fillWidth:true;Layout.minimumWidth:0;placeholderText:Tr.tr("Home, Dock, Laptop…");Accessible.name:Tr.tr("Display profile name");maximumLength:128}
                IconTextButton {text:Tr.tr("Save current layout");icon:"add";disabled:!profileName.text.trim()||Monitors.hasStaged||!!DisplayProfiles.pending||DisplayProfiles.busy;onClicked:{DisplayProfiles.save(profileName.text.trim());profileName.clear();}}
            }
            StyledText {Layout.fillWidth:true;visible:Monitors.hasStaged;text:Tr.tr("Apply and confirm your changes before saving this layout.");wrapMode:Text.WordWrap;color:Colours.palette.m3onSurfaceVariant}
            StyledText {Layout.fillWidth:true;visible:!DisplayProfiles.profiles.length;text:Tr.tr("Save your current setup as a starting point. Connect another display setup to create its own profile.");wrapMode:Text.WordWrap;color:Colours.palette.m3onSurfaceVariant}
            Repeater {
                model:DisplayProfiles.profiles
                SettingsCard {
                    id:profile
                    required property var modelData
                    title:modelData.name
                    icon:modelData.matches?"desktop_windows":"monitor"
                    badge:modelData.id===DisplayProfiles.data.activeProfileId?Tr.tr("Active"):modelData.matches?Tr.tr("Displays connected"):Tr.tr("Different displays")
                    description:(modelData.devices??[]).map(m=>m.description||m.model||m.name).join(" · ")
                    TextFieldRow {label:Tr.tr("Profile name");value:profile.modelData.name;maximumLength:128;onEditingFinished:value=>{if(value.trim()&&value!==profile.modelData.name)DisplayProfiles.update(profile.modelData.id,{name:value});}}
                    Repeater {
                        model:profile.modelData.outputs??[]
                        InfoRow {required property var modelData;label:modelData.name;value:modelData.disabled?Tr.tr("Disabled"):(modelData.mode+" · "+Math.round(modelData.scale*100)+"% · "+modelData.x+", "+modelData.y)}
                    }
                    ToggleRow {text:Tr.tr("Use this profile automatically");checked:profile.modelData.autoApply!==false;onToggled:DisplayProfiles.update(profile.modelData.id,{autoApply:checked})}
                    RowButton {text:Tr.tr("Prefer for this display setup");subtext:Tr.tr("Choose which profile to use when several match the same screens.");icon:profile.modelData.preferred?"star":"star_outline";disabled:profile.modelData.preferred===true;onClicked:DisplayProfiles.update(profile.modelData.id,{preferred:true})}
                    RowLayout {
                        Layout.fillWidth:true
                        IconTextButton {text:Tr.tr("Try this layout");icon:"preview";disabled:!profile.modelData.matches||!!DisplayProfiles.pending||DisplayProfiles.busy;onClicked:{Monitors.revert();DisplayProfiles.apply(profile.modelData.id);}}
                        Item {Layout.fillWidth:true}
                        IconButton {icon:"delete";Accessible.name:Tr.tr("Delete display profile");disabled:!!DisplayProfiles.pending||DisplayProfiles.busy;onClicked:root.deletingProfile=root.deletingProfile===profile.modelData.id?"":profile.modelData.id}
                    }
                    RowButton {visible:root.deletingProfile===profile.modelData.id;text:Tr.tr("Delete this display profile?");icon:"delete_forever";onClicked:{DisplayProfiles.remove(profile.modelData.id);root.deletingProfile="";}}
                }
            }
        }
        SettingsCard {
            title:Tr.tr("Display protection")
            description:Tr.tr("Changes are saved only after confirmation. The independent watchdog restores the previous settings even if the shell restarts.")
            icon:"shield"
            collapsible:true;expanded:false
            StepperRow {label:Tr.tr("Confirmation timeout (seconds)");from:10;to:60;stepSize:5;value:DisplayProfiles.settings.timeout??15;onMoved:value=>DisplayProfiles.configure({timeout:value})}
            ToggleRow {text:Tr.tr("Match connector names too");subtext:Tr.tr("Use this for identical monitors without unique serial numbers. Moving a cable to another port then requires its own profile.");checked:DisplayProfiles.settings.matchPorts??false;onToggled:DisplayProfiles.configure({matchPorts:checked})}
        }
        // Arrangement
        SettingsCard {
            title: Tr.tr("Arrangement")
            icon: "view_quilt"
            visible: Monitors.arranged.length > 0

            Arrangement {
                visible: Monitors.arranged.length > 0
                monitors: Monitors.monitors
                staged: Monitors.staged
                selected: root.current?.name ?? ""
                onSelect: name => root.selected = name
                onMoved: (name, x, y) => Monitors.stagePosition(name, x, y)
            }

            // Per-monitor settings
        }
        SettingsCard {
            title: Tr.tr("Monitor")
            icon: "monitor"
            visible: root.current !== null

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
                subtext: Tr.tr("Opt in for this display. Confirm the image is stable; changes roll back if not confirmed.")
                menuItems: root.vrrItems
                active: root.vrrItems.find(i => i.value === (root.current?.vrr ?? 0)) ?? null
                onSelected: item => Monitors.stageVrr(root.current.name, item.value)
            }

            // Staged changes
            RowLayout {
                visible: Monitors.hasStaged
                enabled: !DisplayProfiles.pending && !DisplayProfiles.busy
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
        }
        SettingsCard {
            title: Tr.tr("Rendering & compatibility")
            icon: "settings"
            collapsible: true
            expanded: false

            SystemSettingsSection {
                keys: ["xwayland.force_zero_scaling", "misc.vfr"]
            }
        }
        SettingsCard {
            title: Tr.tr("Brightness")
            icon: "brightness_6"

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
}
