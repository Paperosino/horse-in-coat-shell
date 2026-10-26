pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Window
import Quickshell.Widgets

IconImage {
    id: root
    // A stable upper bound, not the instantaneous hover scale. No per-frame
    // icon-provider requests while the dock wave or panel transition runs.
    property var rasterRoot: null
    property real rasterScale: rasterRoot?.iconRasterScale ?? 1
    readonly property int rasterExtent: Math.min(512, Math.max(1, Math.ceil(actualSize * Math.max(1, rasterScale))))
    readonly property size effectTextureSize: Qt.size(Math.ceil(width * Math.max(1, rasterScale) * Screen.devicePixelRatio), Math.ceil(height * Math.max(1, rasterScale) * Screen.devicePixelRatio))
    function findRasterRoot(): void {
        rasterRoot = null;
        for (let item = parent; item; item = item.parent)
            if (item.iconRasterScale !== undefined) { rasterRoot = item; return; }
    }
    Component.onCompleted: findRasterRoot()
    onParentChanged: findRasterRoot()
    mipmap: true
    backer.smooth: true
    backer.sourceSize: Qt.size(rasterExtent, rasterExtent)
}
