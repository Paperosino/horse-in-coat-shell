pragma ComponentBehavior: Bound
import QtQuick
import Quickshell
import Quickshell.Io
import qs.services
import qs.utils
Scope {
    id:root
    required property string pluginId
    property bool enabled:false
    property bool restarting:false
    Connections {target:Plugins;function onRevisionChanged():void {if(root.enabled){const wasRunning=process.running;root.restarting=true;if(wasRunning)process.running=false;else restart.start();}}}
    Timer {id:restart;interval:1;onTriggered:{root.restarting=false;process.running=Qt.binding(()=>root.enabled&&!root.restarting);}}
    function sendAction(action: string,value:var):void {
        if(process.running)process.write(JSON.stringify({type:"action",id:action,value:value})+"\n");
    }
    Component.onCompleted:Plugins.registerWorker(pluginId,root)
    Component.onDestruction:Plugins.unregisterWorker(pluginId)
    Process {
        id:process
        command:["python3",Paths.toLocalFile(Qt.resolvedUrl("../../assets/isolated_extension.py")),root.pluginId]
        running:root.enabled&&!root.restarting
        stdinEnabled:true
        stdout:SplitParser {onRead:line=>{try{Plugins.workerState(root.pluginId,JSON.parse(line));}catch(e){Plugins.reportError(root.pluginId,"Invalid extension worker response");}}}
        stderr:StdioCollector {id:errors}
        onExited:(code,status)=>{if(root.restarting){restart.start();return;}if(root.enabled)Plugins.reportError(root.pluginId,errors.text.trim()||"Isolated extension stopped unexpectedly");}
    }
}
