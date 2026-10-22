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
    property real amount:field.hovered && animated ? 1 : 0
    readonly property real baseWidth:240*Tokens.scale
    readonly property real baseHeight:56*Tokens.scale
    readonly property real baseX:(width-baseWidth)/2
    readonly property real baseY:height-baseHeight-12*Tokens.scale
    readonly property real bubbleRadius:28*Tokens.scale
    Behavior on amount {enabled:root.animated;SpringAnimation{spring:4;damping:DockConf.damping;epsilon:0.005}}
    Behavior on cursor {enabled:root.animated;SpringAnimation{spring:4.5;damping:DockConf.damping;epsilon:0.1}}
    BlobGroup {id:surface;color:Colours.palette.m3surfaceContainerHigh;smoothing:28*Tokens.scale}
    BlobRect {group:surface;deformScale:0;x:root.baseX;y:root.baseY;implicitWidth:root.baseWidth;implicitHeight:root.baseHeight;radius:height/2}
    BlobRect {
        visible:root.amount>0.001;group:visible ? surface : null;deformScale:0
        x:Math.max(root.baseX+32*Tokens.scale,Math.min(root.baseX+root.baseWidth-32*Tokens.scale,root.cursor))-root.bubbleRadius
        y:root.baseY+root.baseHeight/2-DockConf.lift*Tokens.scale*root.amount-root.bubbleRadius
        implicitWidth:root.bubbleRadius*2;implicitHeight:implicitWidth;radius:width/2
    }
    Repeater {
        model:["folder","chat_bubble","settings"]
        Item {
            id:icon
            required property string modelData
            required property int index
            readonly property real center:root.width/2+(index-1)*60*Tokens.scale
            readonly property real distance:center-root.cursor
            readonly property real weight:Math.exp(-distance*distance/(2*Math.pow(DockConf.spread*Tokens.scale,2)))*root.amount
            width:40*Tokens.scale;height:width
            x:center-width/2;y:root.baseY+(root.baseHeight-height)/2-DockConf.lift*Tokens.scale*weight
            scale:1+(DockConf.magnification-1)*weight
            StyledRect {
                anchors.fill:parent;radius:14*Tokens.scale
                color:icon.index===1 ? Colours.palette.m3primaryContainer : Colours.palette.m3secondaryContainer
                MaterialIcon {anchors.centerIn:parent;text:icon.modelData;color:Colours.palette.m3onSecondaryContainer;fontStyle:Tokens.font.icon.medium}
            }
        }
    }
    HoverHandler {id:field;onPointChanged:if(hovered)root.cursor=point.position.x}
}
