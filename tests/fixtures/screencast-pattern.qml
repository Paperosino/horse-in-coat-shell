import QtQuick
import Quickshell
ShellRoot {
    settings.watchFiles: false
    FloatingWindow {
        title: "HICS capture fixture"
        visible: true
        implicitWidth: 640
        implicitHeight: 360
        color: "#1d1d2e"
        Rectangle {
            width: 180; height: 280; y: 40
            color: "#cab0fa"
            SequentialAnimation on x {
                loops: Animation.Infinite
                NumberAnimation { from: 0; to: 460; duration: 800 }
                NumberAnimation { from: 460; to: 0; duration: 800 }
            }
        }
    }
}
