pragma ComponentBehavior: Bound
import QtQuick
import Hyprstack.Blobs
import Hyprstack.Config
import qs.components
import qs.services
Item {
    id:root
    implicitHeight:140*Tokens.scale
    readonly property bool animated:DockConf.animations && !GlobalConfig.appearance.reducedMotion
    property real cursor:width/2
    readonly property real baseWidth:240*Tokens.scale
    readonly property real baseHeight:56*Tokens.scale
    readonly property real baseX:(width-baseWidth)/2
    readonly property real baseY:height-baseHeight-12*Tokens.scale
    BlobGroup {id:surface;color:Colours.palette.m3surfaceContainerHigh;smoothing:28*Tokens.scale}
    BlobRect {group:surface;deformScale:0;x:root.baseX;y:root.baseY;implicitWidth:root.baseWidth;implicitHeight:root.baseHeight;radius:height/2}
    Repeater {
        model:["folder","chat_bubble","settings"]
        Item {
            id:icon
            required property string modelData
            required property int index
            readonly property real center:root.width/2+(index-1)*60*Tokens.scale
            readonly property real distance:center-root.cursor
            readonly property real weight:response.value
            MotionSpring {id:response;target:field.hovered && root.animated ? Math.exp(-icon.distance*icon.distance/(2*Math.pow(DockConf.spread*Tokens.scale,2))) : 0;enabled:root.animated;stiffness:360;damping:DockConf.damping}
            width:40*Tokens.scale;height:width
            x:center-width/2;y:root.baseY+(root.baseHeight-height)/2-DockConf.lift*Tokens.scale*weight
            scale:1+(DockConf.magnification-1)*weight
            BlobRect {
                visible:icon.weight>0.015;group:visible?surface:null;deformScale:0
                x:-6*Tokens.scale;y:-6*Tokens.scale
                implicitWidth:icon.width+12*Tokens.scale
                implicitHeight:icon.height+12*Tokens.scale
                radius:20*Tokens.scale
            }
            StyledRect {
                anchors.fill:parent;radius:14*Tokens.scale
                color:icon.index===1 ? Colours.palette.m3primaryContainer : Colours.palette.m3secondaryContainer
                MaterialIcon {anchors.centerIn:parent;text:icon.modelData;color:Colours.palette.m3onSecondaryContainer;fontStyle:Tokens.font.icon.medium}
            }
        }
    }
    HoverHandler {id:field;onPointChanged:if(hovered)root.cursor=point.position.x}
}
