pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Quickshell.Services.Pipewire
import Hyprstack.Services
import Hyprstack.Config
import Hyprstack.I18n
import qs.components
import qs.components.controls
import qs.modules.nexus
import qs.services

Item {
    id: root

    required property PopoutState popouts

    implicitWidth: Tokens.sizes.bar.audioWidth
    implicitHeight: layout.implicitHeight + Tokens.padding.medium * 2

    ButtonGroup {
        id: sinks
    }

    ButtonGroup {
        id: sources
    }

    ColumnLayout {
        id: layout

        anchors.left: parent.left
        anchors.right: parent.right
        anchors.verticalCenter: parent.verticalCenter
        spacing: Tokens.spacing.medium

        StyledText {
            text: Tr.trCtx("Output device", "audio output device")
            font: Tokens.font.body.builders.medium.weight(Font.Medium).build()
        }

        Repeater {
            model: Audio.sinks

            StyledRadioButton {
                id: control

                required property PwNode modelData

                Layout.fillWidth: true
                ButtonGroup.group: sinks
                checked: Audio.sink?.id === modelData.id
                onClicked: Audio.setAudioSink(modelData)
                text: modelData.description
            }
        }

        StyledText {
            Layout.topMargin: Tokens.spacing.medium
            text: Tr.trCtx("Input device", "audio input device")
            font: Tokens.font.body.builders.medium.weight(Font.Medium).build()
        }

        Repeater {
            model: Audio.sources

            StyledRadioButton {
                required property PwNode modelData

                Layout.fillWidth: true
                ButtonGroup.group: sources
                checked: Audio.source?.id === modelData.id
                onClicked: Audio.setAudioSource(modelData)
                text: modelData.description
            }
        }

        StyledText {
            Layout.topMargin: Tokens.spacing.medium
            text: Audio.muted ? Tr.tr("Volume (muted)") : Tr.tr("Volume (%1%)").arg(Math.round(Audio.volume * 100))
            font: Tokens.font.body.builders.medium.weight(Font.Medium).build()
        }

        CustomMouseArea {
            Layout.fillWidth: true
            implicitHeight: Tokens.padding.medium * 3

            onWheel: event => {
                if (event.angleDelta.y > 0)
                    Audio.incrementVolume();
                else if (event.angleDelta.y < 0)
                    Audio.decrementVolume();
            }

            StyledSlider {
                anchors.left: parent.left
                anchors.right: parent.right
                implicitHeight: parent.implicitHeight

                to:GlobalConfig.services.maxVolume
                value: Audio.volume
                onInteraction: value => Audio.setVolume(value)
            }
        }

        IconTextButton {Layout.fillWidth:true;text:Audio.privacyMuted?Tr.tr("Unmute microphones"):Tr.tr("Mute all microphones");icon:Audio.privacyMuted?"mic_off":"mic";onClicked:Audio.setMicrophonePrivacy(!Audio.privacyMuted)}
        RowLayout {
            Layout.fillWidth:true
            StyledText {Layout.fillWidth:true;text:Tr.tr("Camera (PipeWire)");font:Tokens.font.body.small}
            StyledSwitch {checked:!DesktopConveniences.cameraBlocked;enabled:!DesktopConveniences.busy;onToggled:DesktopConveniences.setCameraBlocked(!checked)}
        }
        StyledText {Layout.fillWidth:true;wrapMode:Text.WordWrap;font:Tokens.font.body.small;color:Colours.palette.m3onSurfaceVariant;text:Tr.tr("Camera changes briefly interrupt audio")}
        IconTextButton {Layout.fillWidth:true;text:Tr.tr("Privacy & active capture");icon:"shield";onClicked:WindowFactory.openPage("sharing")}
        IconTextButton {
            Layout.fillWidth: true
            Layout.topMargin: Tokens.spacing.medium
            inactiveColour: Colours.palette.m3primaryContainer
            inactiveOnColour: Colours.palette.m3onPrimaryContainer
            verticalPadding: Tokens.padding.extraSmall
            text: Tr.tr("Open settings")
            icon: "settings"

            onClicked: root.popouts.detachRequested("audio")
        }
    }
}
