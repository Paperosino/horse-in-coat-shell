import QtQuick
import QtMultimedia
import Hyprstack.Services
import qs.services
Item {
    id: root
    required property var settings
    property bool paused: false
    property int restartSerial: 0
    property string outputName
    property int frames: 0
    onRestartSerialChanged: player.restart()
    WallpaperPlayer {
        id: player
        source: LiveWallpapers.videoSource(root.settings)
        paused: root.paused
        muted: root.settings.muted
        volume: root.settings.volume / 100
        videoSink: video.videoSink
        onFrameReceived: root.frames++
    }
    Timer {
        interval: 1000; running: !!root.outputName; repeat: true
        onTriggered: LiveWallpapers.reportVideo(root.outputName, {frames: root.frames, paused: root.paused,
            recoveries: player.recoveries, error: player.error, source: player.source.toString()})
    }
    VideoOutput {
        id: video
        anchors.fill: parent
        fillMode: root.settings.scaling === "fit" ? VideoOutput.PreserveAspectFit : root.settings.scaling === "stretch" ? VideoOutput.Stretch : VideoOutput.PreserveAspectCrop
    }
}
