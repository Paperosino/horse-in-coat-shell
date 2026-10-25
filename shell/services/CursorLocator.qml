pragma Singleton
pragma ComponentBehavior: Bound
import QtQuick
import Quickshell
import Quickshell.Wayland
import Hyprstack.Config
Singleton {
    id: root
    property var output: null
    property point position: Qt.point(0,0)
    property int generation: 0
    function show(): void {
        if(!GlobalConfig.utilities.comfort.cursorLocator)return;
        const request=++generation;
        Hypr.extras.request("j/cursorpos",(ok,text)=>{
            if(!ok||request!==root.generation)return;
            let point;try{point=JSON.parse(text);}catch(error){return;}
            if(!Number.isFinite(point.x)||!Number.isFinite(point.y))return;
            const screen=Quickshell.screens.find(screen=>{
                const monitor=Hypr.monitors.values.find(monitor=>monitor.name===screen.name);
                const geometry=monitor?.lastIpcObject;
                return geometry&&point.x>=geometry.x&&point.x<geometry.x+screen.width&&point.y>=geometry.y&&point.y<geometry.y+screen.height;
            });
            if(!screen)return;
            const monitor=Hypr.monitors.values.find(monitor=>monitor.name===screen.name);
            root.position=Qt.point(point.x-monitor.lastIpcObject.x,point.y-monitor.lastIpcObject.y);root.output=screen;expiry.restart();
        });
    }
    Timer {id:expiry;interval:Math.max(1,Math.min(5,GlobalConfig.utilities.comfort.cursorLocatorSeconds))*1000;onTriggered:root.output=null}
    Variants {
        model:root.output?[root.output]:[]
        PanelWindow {
            required property var modelData
            screen:modelData
            anchors {top:true;bottom:true;left:true;right:true}
            exclusiveZone:0
            WlrLayershell.layer:WlrLayer.Overlay
            WlrLayershell.keyboardFocus:WlrKeyboardFocus.None
            WlrLayershell.namespace:"hics-cursor-locator"
            color:"transparent"
            mask:Region {}
            Rectangle {
                id:ring
                x:root.position.x-width/2;y:root.position.y-height/2
                width:100;height:width;radius:width/2;color:"transparent";border.width:5;border.color:"#ffffff"
                Rectangle {anchors.fill:parent;anchors.margins:6;radius:width/2;color:"transparent";border.width:3;border.color:"#111111"}
                SequentialAnimation on scale {
                    running:!GlobalConfig.appearance.reducedMotion;loops:Animation.Infinite
                    NumberAnimation {from:0.8;to:1.15;duration:500;easing.type:Easing.InOutSine}
                    NumberAnimation {from:1.15;to:0.8;duration:500;easing.type:Easing.InOutSine}
                }
            }
        }
    }
}
