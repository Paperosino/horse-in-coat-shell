//@ pragma AppId org.hics.FontconfigProbe
//@ pragma DefaultEnv QS_DROP_EXPENSIVE_FONTS=1
import QtQuick
import Quickshell
import Quickshell.Io
ShellRoot {
    id: root
    property string filterXml: ""
    property int attempts: 0
    FileView {
        path: Quickshell.env("FONTCONFIG_FILE")
        onLoaded: root.filterXml = text()
    }
    FloatingWindow {
        visible: true
        implicitWidth: 320
        implicitHeight: 120
        Text { anchors.centerIn: parent; text: "Шрифты HICS · Fonts"; font.pixelSize: 22 }
    }
    Timer {
        interval: 100
        repeat: true
        running: true
        onTriggered: {
            ++root.attempts
            if (root.attempts > 100) {
                console.error("PROFILE_FAIL Fontconfig filter not read")
                Qt.exit(1)
                return
            }
            if (!root.filterXml || root.attempts < 10) return
            console.log("FONTCONFIG_RESULT", JSON.stringify({
                xml: root.filterXml,
                families: Qt.fontFamilies().length
            }))
            console.log("PROFILE_COMPLETE", CYCLES)
            Qt.quit()
        }
    }
}
