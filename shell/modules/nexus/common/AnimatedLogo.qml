import QtQuick
import qs.components

Logo {
    id: root
    property bool skipIntroAnimation: false
    signal animationCompleted
    opacity: skipIntroAnimation ? 1 : 0
    scale: skipIntroAnimation ? 1 : 0.92
    ParallelAnimation {
        running: !root.skipIntroAnimation
        onFinished: root.animationCompleted()
        Anim { target: root; property: "opacity"; to: 1; type: Anim.DefaultEffects }
        Anim { target: root; property: "scale"; to: 1; type: Anim.DefaultSpatial }
    }
}
