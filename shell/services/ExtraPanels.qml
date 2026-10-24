pragma Singleton
import QtQuick
import Quickshell
import Hyprstack.Config
import Quickshell.Io
import qs.components
import qs.utils
Singleton {
    id:root
    property var liveHeights:({})
    property var panels:[]
    property var removed:[]
    readonly property bool busy:backend.busy
    readonly property string error:backend.error
    function accept(value:var):void {if(value.error)return;panels=value.panels??[];removed=value.removed??[];}
    function reload():void {backend.call(["list"],null,accept);}
    function add(screen:string):void {backend.call(["add"],{screen:screen},accept);}
    function update(id:string,changes:var):void {backend.call(["update",id],changes,accept);}
    function remove(id:string):void {backend.call(["remove",id],null,accept);}
    function restore(id:string):void {backend.call(["restore",id],null,accept);}
    function publishHeight(id:string,value:real):void {if(Math.abs((liveHeights[id]??0)-value)<0.25)return;liveHeights=Object.assign({},liveHeights,{[id]:value});}
    function forgetHeight(id:string):void {const next=Object.assign({},liveHeights);delete next[id];liveHeights=next;}
    function depth(panel:var):real {return panel.autoHide?(liveHeights[panel.id]??0):panel.thickness*Tokens.scale;}
    function inset(screen:string,edge:string):real {return panels.filter(p=>p.screen===screen&&p.edge===edge).reduce((sum,p)=>sum+depth(p),0);}
    function before(id:string):real {const panel=panels.find(p=>p.id===id);if(!panel)return 0;let value=0;for(const item of onScreen(panel.screen)){if(item.id===id)break;if(item.edge===panel.edge)value+=depth(item);}return value;}
    function onScreen(name:string):var {return panels.filter(p=>p.screen===name).sort((a,b)=>a.order-b.order||a.id.localeCompare(b.id));}
    Component.onCompleted:reload()
    FileView {path:Paths.config+"/panels.json";watchChanges:true;printErrors:false;onFileChanged:root.reload()}
    FeatureBackend {id:backend;helper:"panel_manager.py"}
}
