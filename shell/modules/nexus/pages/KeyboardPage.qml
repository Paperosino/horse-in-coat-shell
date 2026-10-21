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

    title: Tr.tr("Keyboard")
    objectName: "keyboardPage"

    // Layout switching shortcuts (xkb grp: options)
    readonly property list<MenuItem> switchItems: [
        MenuItem {
            // TRANSLATORS: no shortcut for switching keyboard layouts
            text: Tr.trCtx("None", "no layout switching shortcut")
            value: ""
        },
        // TRANSLATORS: key combination names, e.g. "Alt+Shift"
        MenuItem {
            text: Tr.tr("Alt+Shift")
            value: "grp:alt_shift_toggle"
        },
        MenuItem {
            text: Tr.tr("Ctrl+Shift")
            value: "grp:ctrl_shift_toggle"
        },
        MenuItem {
            text: Tr.tr("Win+Space")
            value: "grp:win_space_toggle"
        },
        MenuItem {
            text: Tr.tr("Super+Space")
            value: "grp:super_space_toggle"
        },
        MenuItem {
            text: Tr.tr("Caps Lock")
            value: "grp:caps_toggle"
        },
        MenuItem {
            text: Tr.tr("Alt+Space")
            value: "grp:alt_space_toggle"
        }
    ]

    readonly property list<MenuItem> capsItems: [
        MenuItem {
            // TRANSLATORS: Caps Lock behaves as a regular Caps Lock key
            text: Tr.trCtx("Default", "caps lock key behaviour")
            value: ""
        },
        MenuItem {
            text: Tr.tr("Escape")
            value: "caps:escape"
        },
        MenuItem {
            text: Tr.tr("Super")
            value: "caps:super"
        },
        MenuItem {
            text: Tr.tr("Backspace")
            value: "caps:backspace"
        },
        MenuItem {
            // TRANSLATORS: Caps Lock is disabled
            text: Tr.trCtx("None", "caps lock disabled")
            value: "caps:none"
        }
    ]

    readonly property list<MenuItem> composeItems: [
        MenuItem {
            // TRANSLATORS: no compose key
            text: Tr.trCtx("None", "no compose key")
            value: ""
        },
        MenuItem {
            text: Tr.tr("Right Alt")
            value: "compose:ralt"
        },
        MenuItem {
            text: Tr.tr("Right Ctrl")
            value: "compose:rctrl"
        },
        MenuItem {
            // TRANSLATORS: the context menu key on a keyboard
            text: Tr.trCtx("Menu", "keyboard menu key")
            value: "compose:menu"
        },
        MenuItem {
            text: Tr.tr("Left Win")
            value: "compose:lwin"
        },
        MenuItem {
            text: Tr.tr("Right Win")
            value: "compose:rwin"
        }
    ]

    ColumnLayout {
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.top: parent.top
        width: root.cappedWidth
        spacing: Tokens.spacing.extraSmall / 2

        SectionHeader { first: true; text: Tr.tr("Pointing devices") }
        NavRow { first: true; text: Tr.tr("Mouse"); icon: "mouse"; subtext: Tr.tr("Sensitivity, buttons and scrolling"); onClicked: root.nState.openPage("mouse") }
        NavRow { text: Tr.tr("Touchpad"); icon: "touchpad_mouse"; subtext: Tr.tr("Taps, clicks and scrolling"); onClicked: root.nState.openPage("touchpad") }
        NavRow { text: Tr.tr("Cursor"); icon: "arrow_selector_tool"; subtext: Tr.tr("Visibility, movement and zoom"); onClicked: root.nState.openSubPage(4) }
        NavRow { text: Tr.tr("Gestures"); icon: "swipe"; subtext: Tr.tr("Workspace swipes"); onClicked: root.nState.openSubPage(5) }
        NavRow { last:true;text:Tr.tr("Keyboard shortcuts");subtext:Tr.tr("Keys and mouse actions in one place");icon:"keyboard_keys";onClicked:root.nState.openPage("shortcuts") }

        // Layouts
        SectionHeader {
            first: true
            text: Tr.tr("Layouts")
        }

        Repeater {
            model: KeyboardConf.layoutCodes

            ColumnLayout {
                id: layoutBlock

                required property string modelData
                required property int index

                Layout.fillWidth: true
                Layout.bottomMargin: Tokens.spacing.large
                spacing: 0

                ConnectedRect {
                    Layout.fillWidth: true
                    first: true
                    last: !variantRow.visible
                    implicitHeight: layoutRow.implicitHeight + layoutRow.anchors.margins * 2

                    RowLayout {
                        id: layoutRow

                        anchors.fill: parent
                        anchors.margins: Tokens.padding.medium
                        anchors.leftMargin: Tokens.padding.largeIncreased
                        anchors.rightMargin: Tokens.padding.large
                        spacing: Tokens.spacing.small

                        ColumnLayout {
                            Layout.fillWidth: true
                            Layout.minimumWidth: 0
                            spacing: 0

                            StyledText {
                                Layout.fillWidth: true
                                text: KeyboardConf.nameForLayout(layoutBlock.modelData)
                                font: Tokens.font.body.small
                                elide: Text.ElideRight
                            }

                            StyledText {
                                Layout.fillWidth: true
                                visible: KeyboardConf.nameForLayout(layoutBlock.modelData) !== layoutBlock.modelData
                                text: layoutBlock.modelData
                                color: Colours.palette.m3outline
                                font: Tokens.font.label.small
                            }
                        }

                        IconButton {
                            icon: "keyboard_arrow_up"
                            type: IconButton.Text
                            isRound: true
                            disabled: layoutBlock.index === 0
                            onClicked: KeyboardConf.moveLayout(layoutBlock.index, layoutBlock.index - 1)
                        }

                        IconButton {
                            icon: "keyboard_arrow_down"
                            type: IconButton.Text
                            isRound: true
                            disabled: layoutBlock.index === KeyboardConf.layoutCodes.length - 1
                            onClicked: KeyboardConf.moveLayout(layoutBlock.index, layoutBlock.index + 1)
                        }

                        IconButton {
                            icon: "delete"
                            type: IconButton.Text
                            isRound: true
                            inactiveOnColour: Colours.palette.m3error
                            onClicked: KeyboardConf.removeLayout(layoutBlock.index)
                        }
                    }
                }

                SelectRow {
                    id: variantRow

                    visible: variantMenu.instances.length > 1
                    first: false
                    last: true
                    label: Tr.tr("Variant")
                    subtext: Tr.tr("Key arrangement used by this layout")
                    active: variantMenu.instances.find(item => item.value === (KeyboardConf.variantByLayout[layoutBlock.modelData] ?? "")) ?? null
                    onSelected: item => KeyboardConf.setVariant(layoutBlock.modelData, item.value)

                    menuItems: variantMenu.instances

                    Variants {
                        id: variantMenu

                        model: KeyboardConf.variantsFor(layoutBlock.modelData)

                        MenuItem {
                            required property var modelData

                            text: modelData.name
                            value: modelData.code
                        }
                    }
                }
            }
        }

        NavRow {
            first: true
            last: true
            icon: "add"
            text: Tr.tr("Add layout")
            subtext: Tr.trN("%n layout configured", "%n layouts configured", KeyboardConf.layoutCodes.length)
            onClicked: root.nState.openSubPage(1)
        }

        // Switching
        SectionHeader {
            text: Tr.tr("Switching")
        }

        SelectRow {
            first: true
            last: true
            label: Tr.tr("Shortcut for switching layouts")
            subtext: Tr.tr("Key combination that cycles to the next layout")
            fallbackText: Tr.tr("Custom")
            menuItems: root.switchItems
            active: root.switchItems.find(item => item.value === KeyboardConf.switchOption)
            onSelected: item => KeyboardConf.setSwitchOption(item.value)
        }

        // Caps Lock
        SectionHeader {
            text: Tr.tr("Caps Lock")
        }

        SelectRow {
            first: true
            last: true
            label: Tr.tr("Caps Lock behaviour")
            subtext: Tr.tr("What the Caps Lock key does")
            fallbackText: Tr.tr("Custom")
            menuItems: root.capsItems
            active: root.capsItems.find(item => item.value === KeyboardConf.capsOption)
            onSelected: item => KeyboardConf.setCapsOption(item.value)
        }

        // Compose key
        SectionHeader {
            text: Tr.tr("Compose key")
        }

        SelectRow {
            first: true
            last: true
            label: Tr.tr("Compose key")
            subtext: Tr.tr("Typing this key followed by a sequence, e.g. Compose then \" then a, produces accented characters")
            fallbackText: Tr.tr("Custom")
            menuItems: root.composeItems
            active: root.composeItems.find(item => item.value === KeyboardConf.composeOption)
            onSelected: item => KeyboardConf.setComposeOption(item.value)
        }

        // Typing
        SectionHeader {
            text: Tr.tr("Typing")
        }

        ToggleRow {
            first: true
            text: Tr.tr("Turn on Num Lock at startup")
            subtext: Tr.tr("Applies when a keyboard is connected")
            checked: KeyboardConf.numlock
            onToggled: checked => KeyboardConf.setNumlock(checked)
        }

        StepperRow {
            label: Tr.tr("Repeat delay")
            // TRANSLATORS: ms is the millisecond unit, leave it untranslated
            subtext: Tr.tr("Time a key must be held before it starts repeating (ms)")
            value: KeyboardConf.repeatDelay / 1
            from: 100
            to: 2000
            stepSize: 50
            onMoved: value => KeyboardConf.setRepeatDelay(Math.round(value))
        }

        StepperRow {
            last: true
            label: Tr.tr("Repeat rate")
            subtext: Tr.tr("How many times a held key repeats per second")
            value: KeyboardConf.repeatRate / 1
            from: 1
            to: 60
            stepSize: 1
            onMoved: value => KeyboardConf.setRepeatRate(Math.round(value))
        }

        // Configuration
        SectionHeader {
            text: Tr.tr("Configuration")
        }

        InfoRow {
            first: true
            label: "kb_layout"
            value: KeyboardConf.layoutCsv
        }

        InfoRow {
            last: true
            label: "kb_options"
            value: KeyboardConf.optionsCsv || Tr.trCtx("None", "no xkb options")
        }
    }
}
