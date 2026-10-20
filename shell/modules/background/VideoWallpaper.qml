import QtQuick
import QtMultimedia
import Hyprstack.Config
import qs.services
import qs.utils

Item {
    id: root
    required property var settings
    property bool paused: false
    MediaPlayer {
        id: player
        source: Paths.fileUrl(root.settings.source)
        loops: MediaPlayer.Infinite
        autoPlay: !root.paused
        videoOutput: video
        audioOutput: AudioOutput { muted: root.settings.muted; volume: root.settings.volume / 100 }
        onErrorOccurred: (error, errorString) => { LiveWallpapers.playbackError = errorString; }
        Component.onCompleted: root.paused ? pause() : play()
    }
    onPausedChanged: paused ? player.pause() : player.play()
    VideoOutput {
        id: video
        anchors.fill: parent
        fillMode: root.settings.scaling === "fit" ? VideoOutput.PreserveAspectFit : root.settings.scaling === "stretch" ? VideoOutput.Stretch : VideoOutput.PreserveAspectCrop
    }
}
