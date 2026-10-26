pragma ComponentBehavior: Bound
import QtQuick
import Quickshell
import Hyprstack.Config
import qs.components
import qs.services
import qs.modules.bar
import qs.modules.bar.popouts as Popouts
import qs.modules.background
import qs.modules.nexus

ShellRoot {
    id: root
    property int phase: 0
    property real originalHeight: 0
    function check(value, message) { if (!value) { console.error("DESIGN_FAIL", message); Qt.exit(1); } return value; }
    function named(item,name) { if(item.objectName===name)return item;for(const child of item.children??[]){const result=named(child,name);if(result)return result;}return null; }
    FloatingWindow {
        id: win
        visible: true
        implicitWidth: 1000
        implicitHeight: 400
        color: "#202438"
        contentItem.Config.screen: screen.name
        contentItem.Tokens.screen: screen.name
        ScreenState { id: state; modelData: win.screen }
        Popouts.Wrapper { id: popout; screen: win.screen; offsetScale: 0 }
        BarWrapper {
            id: bar
            width: parent.width
            height: implicitHeight
            screen: win.screen
            screenState: state
            popouts: popout
            fullscreen: false
        }
        ShellState.ComponentRef { screen:win.screen; slot:"bar"; component:bar }
    }
    Background { id: background }
    Timer {
        interval: 450
        repeat: true
        running: true
        onTriggered: {
            const step=root.phase++;
            if(step===0){GlobalConfig.appearance.reducedMotion=true;GlobalConfig.bar.scale=1;GlobalConfig.background.desktopIcons.enabled=true;}
            if(step===1){root.originalHeight=bar.contentWidth;GlobalConfig.bar.scale=.75;}
            if(step===2){
                if(!root.check(Math.abs(bar.contentWidth-root.originalHeight*.75)<1,"panel height did not scale"))return;
                if(!root.check(Math.abs(bar.content.width*.75-bar.width)<1,"scaled content no longer spans the panel"))return;
                if(!root.check(Math.abs(bar.content.y)<1,"scaled panel clips its icons"))return;
                if(!root.check(Math.abs(bar.content.scale-.75)<.01,"panel icons did not scale"))return;
                const grid=ShellState.componentsFor(win.screen)?.background?.contentItem;
                function findGrid(item){if(item.objectName==="desktopIconGrid")return item;for(const child of item.children??[]){const result=findGrid(child);if(result)return result;}return null;}
                const icons=grid?findGrid(grid):null;
                if(!root.check(!!icons && icons.y>=bar.contentWidth+15,"desktop grid overlaps the status panel"))return;
                bar.openContext(20);
            }
            if(step===3){
                const menu=bar.settingsMenu;
                if(!root.check(!!menu&&menu.visible&&menu.actions.some(action=>action.page==="statusbar-layout"),"panel context menu failed to open: "+menu+" / "+menu.visible))return;
                if(!root.check(menu.actions.some(action=>action.label==="Widget settings"),"widget context settings are missing"))return;
                menu.contentItem.grabToImage(result=>result.saveToFile("/tmp/hics-panel-context.png"));
                bar.atBottom=true;
            }
            if(step===4){GlobalConfig.bar.height=32;}
            if(step===5){
                if(!root.check(Math.abs(bar.contentWidth-32*bar.Tokens.scale)<1,"manual panel height ignored"))return;
                if(!root.check(Math.abs(bar.content.y)<1,"manual height clips scaled icons"))return;
                GlobalConfig.bar.height=24;
            }
            if(step===6){
                if(!root.check(Math.abs(bar.contentWidth-24*bar.Tokens.scale)<1,"minimum manual panel height ignored"))return;
                GlobalConfig.bar.height=0;
            }
            if(step===7){
                bar.settingsMenu.visible=false;
                const contents=ShellState.componentsFor(win.screen)?.background?.contentItem;
                function grid(item){if(item.objectName==="desktopIconGrid")return item;for(const child of item.children??[]){const result=grid(child);if(result)return result;}return null;}
                const icons=grid(contents);
                if(!root.check(icons.anchors.bottomMargin>=bar.contentWidth+15,"desktop grid overlaps bottom panel"))return;
                GlobalConfig.bar.scale=1;GlobalConfig.background.desktopIcons.enabled=false;
                console.log("SETTINGS_DESIGN_OK");Qt.quit();
            }
        }
    }
}
