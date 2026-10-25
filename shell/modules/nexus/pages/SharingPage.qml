pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import Hyprstack.Config
import Hyprstack.I18n
import Hyprstack.Services
import qs.services
import qs.modules.nexus.common

PageBase {
    id: root
    pageIcon: "screen_share"
    title: Tr.tr("Screen capture & sharing")
    Component.onCompleted: Recorder.refCount++
    Component.onDestruction: Recorder.refCount--
    ColumnLayout {
        anchors.horizontalCenter: parent.horizontalCenter
        width: root.cappedWidth
        spacing: Tokens.spacing.large
        SettingsCard {
            title:Tr.tr("Microphone & camera privacy")
            icon:"shield"
            ToggleRow {first:true;last:true;text:Tr.tr("Mute all microphones");checked:Audio.privacyMuted;onToggled:Audio.setMicrophonePrivacy(checked)}
            ToggleRow {first:true;last:true;text:Tr.tr("Disable camera access through PipeWire");subtext:Tr.tr("Restarts WirePlumber and briefly interrupts audio. Applications using /dev/video directly are not blocked; use a hardware shutter for a global camera switch.");checked:DesktopConveniences.cameraBlocked;enabled:!DesktopConveniences.busy;onToggled:DesktopConveniences.setCameraBlocked(checked)}
            Repeater {model:Audio.microphoneStreams;InfoRow {required property var modelData;first:true;last:true;label:Audio.getStreamName(modelData);value:modelData.audio?.muted?Tr.tr("Microphone stream muted"):Tr.tr("Audio capture stream")}}
            FeatureError {error:DesktopConveniences.error}
        }
        InfoRow {
            first: true
            last: true
            label: Tr.tr("Screen sharing")
            value: Tr.tr("Start sharing in your application. The desktop portal lets you select a screen or window and controls access.")
        }
        InfoRow {
            first: true
            last: true
            label: Tr.tr("Desktop portal")
            value: DesktopIntegration.portalSourceTypes === 0 ? Tr.tr("Screen sharing portal is unavailable") : (DesktopIntegration.portalSourceTypes & 2) ? Tr.tr("Screen and window selection is supported") : Tr.tr("Screen selection is supported")
        }
        SettingsCard {
            title: Tr.tr("Screen recording")
            icon: "screen_share"

            ToggleRow {
                id: sound
                first: true
                text: Tr.tr("Record system audio")
            }
            RowButton {
                text: Tr.tr("Select recording region")
                icon: "crop"
                disabled: Recorder.busy
                onClicked: Recorder.start(sound.checked ? ["-r", "-s"] : ["-r"])
            }
            Repeater {
                model: DesktopIntegration.recordingSources
                RowButton {
                    required property var modelData
                    text: modelData.label
                    subtext: modelData.window ? Tr.tr("Records the current window rectangle, including anything covering it") : Tr.tr("Record this screen")
                    icon: modelData.window ? "window" : "monitor"
                    disabled: Recorder.busy
                    onClicked: Recorder.start(["-r", modelData.geometry, ...(sound.checked ? ["-s"] : [])])
                }
            }
            RowButton {
                visible: Recorder.busy
                text: Tr.tr("Stop recording")
                icon: "stop"
                last: true
                disabled: Recorder.controlBusy
                onClicked: Recorder.stop()
            }
            FeatureError {
                error: Recorder.lastError
            }
        }
        SettingsCard {
            title: Tr.tr("Video capture streams")
            icon: "screen_share"

            InfoRow {
                first: true
                last: true
                label: Tr.tr("Capture status")
                value: !DesktopIntegration.captureMonitorAvailable ? Tr.tr("PipeWire capture monitoring is unavailable") : DesktopIntegration.captureStreams.length ? Tr.tr("Applications currently have video capture streams") : Tr.tr("No video capture streams detected")
            }
            Repeater {
                model: DesktopIntegration.captureStreams
                InfoRow {
                    required property var modelData
                    first: true
                    last: true
                    label: modelData.application
                    value: (modelData.screen ? Tr.tr("Screen capture") : Tr.tr("Video capture (screen or camera)")) + " · " + modelData.state
                }
            }
        }
    }
}
