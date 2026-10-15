import QtQuick
import QtQuick.Shapes
import qs.services

Item {
    id: root
    property color topColour: Colours.palette.m3primary
    property color bottomColour: Colours.palette.m3onSurface
    implicitWidth: 96
    implicitHeight: 96

    Shape {
        anchors.centerIn: parent
        width: 96
        height: 96
        scale: Math.min(root.width / width, root.height / height)
        preferredRendererType: Shape.CurveRenderer
        ShapePath {
            fillColor: root.bottomColour
            strokeColor: "transparent"
            PathSvg { path: "M12 20H68V28H20V60H12Z M24 32H80V40H32V72H24Z" }
        }
        ShapePath {
            fillColor: root.topColour
            strokeColor: "transparent"
            fillRule: ShapePath.OddEvenFill
            PathSvg { path: "M36 44H92V84H36Z M44 52V76H84V52Z" }
        }
        ShapePath {
            fillColor: root.topColour
            strokeColor: "transparent"
            PathSvg { path: "M52 56H58V61H70V56H76V72H70V67H58V72H52Z" }
        }
    }
}
