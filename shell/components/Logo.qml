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
            strokeWidth: 0
            PathSvg { path: "M18 87 25 62 37 53 59 52 74 64 82 87Z" }
        }
        ShapePath {
            fillColor: Colours.palette.m3surface
            strokeColor: "transparent"
            strokeWidth: 0
            PathSvg { path: "m28 65 13-10 9 14-10 18H23Zm29-11 14 12 8 21H50Z" }
        }
        ShapePath {
            fillColor: root.topColour
            strokeColor: "transparent"
            strokeWidth: 0
            PathSvg { path: "m41 57 8 11-5 17 13-18-2-13Z" }
        }
        ShapePath {
            fillColor: root.topColour
            strokeColor: "transparent"
            strokeWidth: 0
            PathSvg { path: "m29 55 3-16 6-8 1-15 8 8 8-13 4 17 11 8 12 7 3 9-7 9-17-2-9-8-4 12Z" }
        }
        ShapePath {
            fillColor: Colours.palette.m3surface
            strokeColor: "transparent"
            strokeWidth: 0
            PathSvg { path: "m29 58-3-9 5-9-5 2 6-12-3 1 8-14 3 12 7-9-2 13-8 12-1 12Z" }
        }
        ShapePath {
            fillColor: root.bottomColour
            strokeColor: "transparent"
            strokeWidth: 0
            PathSvg { path: "m52 21 3-3 1 10-5-2Z" }
        }
        ShapePath {
            fillColor: Colours.palette.m3surface
            strokeColor: "transparent"
            strokeWidth: 0
            PathSvg { path: "m40 37 30 3-1 4-8-1-3 7-10-2-3-7-6-1Z" }
        }
        ShapePath {
            fillColor: "transparent"
            strokeColor: Colours.palette.m3surface
            strokeWidth: 3
            PathSvg { path: "m59 41 5 1" }
        }
        ShapePath {
            fillColor: "transparent"
            strokeColor: Colours.palette.m3surface
            strokeWidth: 2
            PathSvg { path: "m68 58 10 1" }
        }
        ShapePath {
            fillColor: "transparent"
            strokeColor: root.topColour
            strokeWidth: 2
            PathSvg { path: "m38 57 9 11-9 6 4 12m19-31-8 12 7 7-8 12" }
        }
        ShapePath {
            fillColor: Colours.palette.m3surface
            strokeColor: "transparent"
            PathSvg { path: "M79 50A2 2.5 0 1 1 75 50A2 2.5 0 1 1 79 50Z" }
        }
    }
}
