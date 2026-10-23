pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import Hyprstack.Config
import Hyprstack.I18n
import Hyprstack.Services
import qs.components.controls
import qs.modules.nexus.common

ColumnLayout {
    id: root
    Layout.fillWidth: true
    spacing: Tokens.spacing.extraSmall / 2
    Component.onDestruction: DesktopIntegration.stopMicrophoneTest()
    SettingsCard {
        title: Tr.tr("Microphone test")
        icon: "mic"

        RowButton {
            first: true
            text: DesktopIntegration.microphoneTesting ? Tr.tr("Stop microphone test") : Tr.tr("Test default microphone")
            subtext: Tr.tr("Shows the input level for 15 seconds. Audio is not saved.")
            icon: "mic"
            onClicked: DesktopIntegration.microphoneTesting ? DesktopIntegration.stopMicrophoneTest() : DesktopIntegration.startMicrophoneTest()
        }
        InfoRow {
            last: true
            label: Tr.tr("Input level")
            value: Math.round(DesktopIntegration.microphoneLevel * 100) + "%"
        }
    }
    SettingsCard {
        title: Tr.tr("Device profiles")
        icon: "speaker_group"

        Repeater {
            model: DesktopIntegration.cards
            SelectRow {
                id: card
                required property var modelData
                property var choices: []
                first: true
                last: true
                label: modelData.description || modelData.name
                subtext: Tr.tr("Changing a profile may disconnect audio streams")
                menuItems: choices
                active: choices.find(p => p.value === modelData.active) ?? null
                function rebuild(): void {
                    const old = choices;
                    choices = (modelData.profiles ?? []).map(p => menuItem.createObject(card, {
                            text: p.description || p.name,
                            value: p.name
                        }));
                    for (const item of old)
                        item.destroy();
                }
                onModelDataChanged: rebuild()
                Component.onCompleted: rebuild()
                onSelected: item => DesktopIntegration.setCardProfile(modelData.name, item.value)
                Component {
                    id: menuItem
                    MenuItem {}
                }
            }
        }
        FeatureError {
            error: DesktopIntegration.error
        }
    }
}
