pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import Hyprstack.Services
import Hyprstack.Config
import Hyprstack.I18n
import qs.services
import qs.utils
import qs.modules.nexus.common

PageBase {
    id: root
    pageIcon: "volume_up"

    title: Tr.tr("Audio")

    ColumnLayout {
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.top: parent.top
        width: root.cappedWidth
        spacing: Tokens.spacing.large

        SettingsCard {
            title: Tr.trCtx("Output", "audio output")
            icon: "speaker"

            SliderRow {
                first: true
                icon: Icons.getVolumeIcon(Audio.volume, Audio.muted)
                label: Tr.trCtx("Output", "audio output")
                valueLabel: Strings.percentOne(value)
                to:GlobalConfig.services.maxVolume
                value: Audio.volume
                enabled: !Audio.muted
                onMoved: v => Audio.setVolume(v)
            }

            ToggleRow {text:Tr.tr("Allow volume above 100%");subtext:Tr.tr("Raises the limit to 150%; high levels may distort sound");checked:GlobalConfig.services.maxVolume>1;onToggled:{GlobalConfig.services.maxVolume=checked?1.5:1;if(Audio.sink?.audio&&Audio.volume>GlobalConfig.services.maxVolume)Audio.sink.audio.volume=GlobalConfig.services.maxVolume;}}
            ToggleRow {
                text: Tr.trCtx("Muted", "audio output muted")
                checked: Audio.muted
                onToggled: Audio.setStreamMuted(Audio.sink, checked)
            }

            SliderRow {visible:Audio.stereoOutput;label:Tr.tr("Balance · left / right");icon:"tune";from:-1;to:1;value:Audio.balance;valueLabel:Math.abs(value)<0.01?Tr.tr("Centre"):Math.round(Math.abs(value)*100)+"% "+(value<0?Tr.tr("Left"):Tr.tr("Right"));onMoved:v=>Audio.setBalance(v)}
            RowButton {text:Tr.tr("Test left speaker");icon:"speaker";disabled:DesktopConveniences.speakerTesting;onClicked:DesktopConveniences.testSpeaker(0)}
            RowButton {text:Tr.tr("Test right speaker");icon:"speaker";disabled:DesktopConveniences.speakerTesting;onClicked:DesktopConveniences.testSpeaker(1)}
            FeatureError {error:DesktopConveniences.error}
            AudioDeviceList {
                nodes: Audio.sinks
                currentId: Audio.sink?.id ?? -1
                iconName: "speaker"
                placeholderIcon: "speaker"
                placeholderText: Tr.trCtx("No output devices", "no audio outputs")
                onSelected: node => Audio.setAudioSink(node)
            }
        }
        SettingsCard {
            title: Tr.trCtx("Input", "audio input")
            icon: "mic"

            SliderRow {
                first: true
                icon: Icons.getMicVolumeIcon(Audio.sourceVolume, Audio.sourceMuted)
                label: Tr.trCtx("Input", "audio input")
                valueLabel: Strings.percentOne(value)
                value: Audio.sourceVolume
                enabled: !Audio.sourceMuted
                onMoved: v => Audio.setSourceVolume(v)
            }

            ToggleRow {
                text: Tr.trCtx("Muted", "audio input muted")
                checked: Audio.sourceMuted
                onToggled: Audio.setStreamMuted(Audio.source, checked)
            }

            AudioDeviceList {
                nodes: Audio.sources
                currentId: Audio.source?.id ?? -1
                iconName: "mic"
                placeholderIcon: "mic_off"
                placeholderText: Tr.trCtx("No input devices", "no audio inputs")
                onSelected: node => Audio.setAudioSource(node)
            }
        }
        AudioTools {}

        // Per-app volumes
        NavRow {
            Layout.topMargin: Tokens.spacing.large - parent.spacing
            first: true
            last: true

            icon: "tune"
            text: Tr.tr("App volumes")
            subtext: Audio.streams.length === 0 ? Tr.tr("No apps playing audio") : Tr.trN("%n app playing audio", "%n apps playing audio", Audio.streams.length)
            onClicked: root.nState.openSubPage(1)
        }
        SettingsCard {
            title: Tr.tr("Volume")
            icon: "volume_up"

            StepperRow {
                first: true
                label: Tr.tr("Volume step")
                subtext: Tr.tr("Amount the volume changes per scroll (%)")
                value: Math.round(GlobalConfig.services.audioIncrement * 100)
                from: 1
                to: 50
                stepSize: 1
                onMoved: v => GlobalConfig.services.audioIncrement = v / 100
            }

            StepperRow {
                last: true
                label: Tr.tr("Max volume")
                subtext: Tr.tr("Upper limit for output volume (%)")
                value: Math.round(GlobalConfig.services.maxVolume * 100)
                from: 50
                to: 200
                stepSize: 5
                onMoved: v => GlobalConfig.services.maxVolume = v / 100
            }

            NavRow {
                first: true
                last: true
                text: Tr.tr("Media & lyrics")
                icon: "music_note"
                onClicked: root.nState.openSubPage(2)
            }
        }
    }
}
