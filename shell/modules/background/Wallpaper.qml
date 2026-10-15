pragma ComponentBehavior: Bound

import QtQuick
import Hyprstack.Config
import qs.components
import qs.components.images
import qs.services

StyledRect {
    id: root

    color: Colours.palette.m3surfaceContainer

    property string source: Wallpapers.current
    property CachingImage current

    onSourceChanged: {
        if (!source) {
            if (current)
                current.destroy();
            current = null;
        } else {
            current = imgComp.createObject(this, {
                path: source
            });
        }
    }

    Component.onCompleted: {
        if (source)
            Qt.callLater(() => {
                current = imgComp.createObject(this, {
                    path: source
                });
            });
    }

    Component {
        id: imgComp

        CachingImage {
            id: img

            anchors.fill: parent

            opacity: 0

            onStatusChanged: {
                if (status === Image.Ready)
                    anim.start();
            }

            Anim on opacity {
                id: anim

                type: Anim.SlowEffects
                running: false
                from: 0
                to: 1
            }

            Timer {
                running: root.current !== img && root.current?.status === Image.Ready
                interval: anim.duration
                onTriggered: img.destroy()
            }
        }
    }
}
