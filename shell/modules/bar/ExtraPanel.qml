pragma ComponentBehavior: Bound
import QtQuick
import Quickshell
import Quickshell.Wayland
import Quickshell.Hyprland
import Hyprstack.Config
import qs.components
import qs.components.containers
import qs.services
import qs.modules.bar.popouts as Popouts
StyledWindow {
    id:root
    required property var spec
    required property real edgeOffset
    Component.onDestruction:ExtraPanels.forgetHeight(spec.id)
    name:"panel-"+spec.id
    anchors {left:true;right:true;top:true;bottom:true}
    exclusionMode:ExclusionMode.Ignore
    WlrLayershell.layer:WlrLayer.Top
    WlrLayershell.keyboardFocus:popup.content.hasCurrent?WlrKeyboardFocus.OnDemand:WlrKeyboardFocus.None
    contentItem.Config.screen:"panel-"+spec.id
    readonly property bool atBottom:spec.edge==="bottom"
    readonly property var monitor:Hypr.monitorFor(screen)
    readonly property bool fullscreen:monitor?.activeWorkspace?.toplevels.values.some(w=>w.lastIpcObject.fullscreen>0)??false
    mask:popup.content.hasCurrent?null:inputRegion
    Region {id:inputRegion;Region {item:bar} Region {item:trigger}}
    ScreenState {
        id:state;modelData:root.screen
        function forward(key:string):void {if(!state[key])return;ShellState.forScreen(root.screen)[key]=true;state[key]=false;}
        onLauncherChanged:forward("launcher")
        onDashboardChanged:forward("dashboard")
        onSessionChanged:forward("session")
        onSidebarChanged:forward("sidebar")
    }
    StyledRect {
        x:bar.x;y:bar.y;width:bar.width;height:bar.height
        visible:bar.visible
        color:Colours.tPalette.m3surfaceContainerLow
        radius:Tokens.rounding.large
    }
    Item {
        id:popupArea
        x:0;y:root.atBottom?0:bar.y+bar.height
        width:root.width;height:root.atBottom?bar.y:root.height-y
        StyledRect {
            x:popup.x;y:popup.y;width:popup.width;height:popup.height
            visible:popup.visible
            radius:Tokens.rounding.extraLarge;color:Colours.tPalette.m3surfaceContainerLow
        }
        Popouts.ClipWrapper {id:popup;screen:root.screen;borderThickness:0;atBottom:root.atBottom}
    }
    BarWrapper {
        id:bar
        screen:root.screen;screenState:state;popouts:popup.content;fullscreen:root.fullscreen
        atBottom:root.atBottom
        desktopFrame:false
        thicknessOverride:root.spec.thickness*Tokens.scale
        onHeightChanged:ExtraPanels.publishHeight(root.spec.id,root.fullscreen?0:height)
        y:root.atBottom?root.height-height-root.edgeOffset:root.edgeOffset
        width:root.width
    }
    Item {
        id:trigger
        x:0;y:root.atBottom?root.height-root.edgeOffset-3*Tokens.scale:root.edgeOffset
        width:root.width;height:root.fullscreen?0:3*Tokens.scale
        HoverHandler {onHoveredChanged:{if(hovered){state.bar=true;hideDelay.stop();}else hideDelay.restart();}}
    }
    HoverHandler {
        id:barHover;parent:bar
        blocking:false
        onHoveredChanged:{bar.isHovered=hovered;if(hovered)hideDelay.stop();else hideDelay.restart();}
        onPointChanged:if(hovered)bar.checkPopout(point.position.x,point.position.y)
    }
    WheelHandler {parent:bar;onWheel:event=>bar.handleWheel(event.x,event.angleDelta)}
    Timer {id:hideDelay;interval:root.spec.hideDelay;onTriggered:if(!barHover.hovered&&!popup.hovered){state.bar=false;bar.isHovered=false;popup.content.close();}}
    Connections {target:popup;function onHoveredChanged():void {if(popup.hovered)hideDelay.stop();else hideDelay.restart();}}
    TapHandler {
        onTapped:point=>{
            const p=point.position;
            const q=popup.mapFromItem(root.contentItem,p.x,p.y);
            if(!bar.contains(bar.mapFromItem(root.contentItem,p.x,p.y))&&!popup.contains(q))popup.content.close();
        }
    }
    HyprlandFocusGrab {active:popup.content.hasCurrent;windows:[root];onCleared:popup.content.close()}
}
