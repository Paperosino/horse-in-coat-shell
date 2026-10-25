pragma ComponentBehavior: Bound
import QtQuick
import Hyprstack.Services
import Hyprstack.I18n
import qs.components
Item {
    id: root
    required property string section
    property var state: ({})
    property bool watching: false
    property string issue
    property var discoveredPrinters: []
    property bool discovered: false
    property bool managedBusy:false
    property string managedError:""
    readonly property bool busy: backend.busy||managedBusy
    readonly property string error: {
        if(managedError)return Tr.tr(managedError);
        if (!backend.error) return "";
        if (issue === "daemon-unavailable") return Tr.tr("System settings service is unavailable");
        if (issue === "cups-unavailable") return Tr.tr("Printing service is unavailable");
        if (issue === "denied") return Tr.tr("Authorization was cancelled or denied");
        if (issue === "unavailable") return Tr.tr("This feature is not available on this system");
        return Tr.tr(backend.error);
    }
    signal applied(string operation)
    visible: false
    function accept(data: var): void { issue = data.code ?? ""; if (!data.error) state = data; }
    function reload(): void { backend.call(["status", section], null, accept); }
    function apply(operation: string, options: var): void {
        const background=section==="storage"&&["clean-packages","clean-coredumps","trim","defragment"].includes(operation);
        if(background){managedBusy=true;managedError="";DesktopJobs.request("maintenance.disk",{operation,options},value=>{root.managedBusy=false;root.managedError=value.error??"";root.reload();if(!value.error)root.applied(operation);},root);return;}
        backend.call(["apply", section, operation], options, data => {
            if (data.ok) { root.reload(); root.applied(operation); return; }
            root.accept(data);
            if (!data.error) root.applied(operation);
        });
    }
    function discoverPrinters(): void {
        backend.call(["status", "printer-discovery"], null, data => {
            root.issue = data.code ?? "";
            if (!data.error) { root.discoveredPrinters = data.devices ?? []; root.discovered = true; }
        });
    }
    Component.onCompleted: reload()
    FeatureBackend { id: backend; executable: "hics-systemctl" }
    Timer { interval: 15000; repeat: true; running: root.watching; onTriggered: { if (!root.busy) root.reload(); } }
}
