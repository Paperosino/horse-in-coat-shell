import QtQuick
import Hyprstack.Services
QtObject {
 id:root
 property int pending:0
 readonly property bool busy:pending>0
 property string error:""
 function call(operation:string,options:var,callback=null):void {
  pending++;error="";
  DesktopJobs.request(operation,options??{},result=>{root.pending--;root.error=result.error??"";if(callback)callback(result);},root);
 }
}
