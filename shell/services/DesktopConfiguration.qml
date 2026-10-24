pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Io
import qs.components
Singleton {
 id:root
 property var data:({settings:{},history:[],profiles:[],presets:[],pending:{}})
 property var preview:({})
 readonly property string error:backend.error
 readonly property bool busy:backend.busy
 readonly property var pending:data.pending?.token?data.pending:null
 property int secondsLeft:0
 function accept(d:var):void {if(d.error)return;data=d;if(d.preview)preview=d.preview;countdown();}
 function call(op:string,value=null,callback=null):void {backend.call([op],value,d=>{accept(d);if(callback)callback(d);});}
 function confirm():void {if(pending)call("confirm",{token:pending.token});}
 function revert():void {if(pending)call("revert",{token:pending.token});}
 function refresh():void {call("status");}
 function countdown():void {secondsLeft=pending?Math.max(0,Math.ceil(pending.deadline-Date.now()/1000)):0;}
 Component.onCompleted:refresh()
 Timer {interval:250;repeat:true;running:!!root.pending;onTriggered:root.countdown()}
 FileView {path:root.data.statePath??"";watchChanges:true;printErrors:false;onFileChanged:reload();onLoaded:{try{root.accept(JSON.parse(text()));}catch(e){}}}
 FeatureBackend {id:backend;helper:"configuration_manager.py"}
}
