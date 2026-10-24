pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Io
import qs.components
import qs.utils
Singleton {
 id:root
 property var data:({controls:{side:"right",order:["minimize","maximize","close"]},rules:[],deviceRules:[],windows:[],devices:[]})
 readonly property string error:backend.error
 readonly property bool busy:backend.busy
 function refresh():void {call("status");}
 function call(op:string,value=null):void {backend.call([op],value,d=>{if(!d.error)data=d;});}
 Component.onCompleted:refresh()
 FeatureBackend {id:backend;helper:"desktop_rules.py"}
 FileView {path:Paths.config+"/application-rules.json";watchChanges:true;printErrors:false;onFileChanged:root.refresh()}
 FileView {path:Paths.config+"/window-controls.json";watchChanges:true;printErrors:false;onFileChanged:root.refresh()}
 FileView {path:Paths.config+"/device-rules.json";watchChanges:true;printErrors:false;onFileChanged:root.refresh()}
}
