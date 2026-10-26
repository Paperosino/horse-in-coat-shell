pragma ComponentBehavior: Bound

import QtQuick
import qs.components
import Hyprstack.Images

ScalableIcon {
    id: root

    required property color colour

    asynchronous: true

    layer.textureSize: effectTextureSize
    layer.smooth: true
    layer.mipmap: true
    layer.enabled: true
    layer.effect: Colouriser {
        sourceColor: analyser.dominantColour
        colorizationColor: root.colour
    }

    layer.onEnabledChanged: {
        if (layer.enabled && status === Image.Ready)
            analyser.requestUpdate();
    }

    onStatusChanged: {
        if (layer.enabled && status === Image.Ready)
            analyser.requestUpdate();
    }

    ImageAnalyser {
        id: analyser

        sourceItem: root
    }
}
