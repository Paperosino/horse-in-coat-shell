pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Io
import qs.components
import qs.utils
Singleton {
    id: root
    property var data: ({settings:{autoApply:true,timeout:15,matchPorts:false},profiles:[],connected:[],pending:null})
    readonly property var profiles: data.profiles ?? []
    readonly property var settings: data.settings ?? ({})
    readonly property var pending: data.pending ?? null
    readonly property string error: backend.error || data.error || ""
    readonly property bool busy: backend.busy
    readonly property string notice: data.notice ?? ""
    property int secondsLeft: 0
    function accept(value: var): void {
        if (!value?.statePath || Number(value.revision??0)<Number(data.revision??0)) return;
        if (Number(value.revision??0)>Number(data.revision??0) && !value.error && !backend.busy)
            backend.error="";
        data=value;
        updateCountdown();
    }
    function updateCountdown(): void {secondsLeft=pending?Math.max(0,Math.ceil(pending.deadline-Date.now()/1000)):0;}
    function call(operation: string, value = null): void {backend.call([operation],value,accept);}
    function refresh(): void {call("status");}
    function preview(patches: var): void {call("preview",{patches:patches});}
    function save(name: string): void {call("save",{name:name});}
    function apply(id: string): void {call("apply",{id:id});}
    function update(id: string, changes: var): void {call("update",{id:id,changes:changes});}
    function remove(id: string): void {call("delete",{id:id});}
    function configure(changes: var): void {call("configure",changes);}
    function confirm(): void {if(pending)call("confirm",{token:pending.token});}
    function revert(): void {if(pending)call("revert",{token:pending.token});}
    Component.onCompleted: refresh()
    Timer {interval:250;running:!!root.pending;repeat:true;onTriggered:root.updateCountdown()}
    FileView {
        path:root.data.statePath??""
        watchChanges:true;printErrors:false
        onFileChanged:reload()
        onLoaded:{try{root.accept(JSON.parse(text()));}catch(e){}}
    }
    FeatureBackend {id:backend;helper:"display_profiles.py"}
}
