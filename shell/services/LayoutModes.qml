pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Io
import Hyprstack.I18n
import Hyprstack.Config
import qs.components
import qs.services
import qs.utils
Singleton {
    id: root
    property var config: ({})
    readonly property string mode: Hypr.layoutMode
    readonly property bool busy: backend.busy
    readonly property string error: backend.error
    readonly property var modes: [
        {id:"tiling",label:Tr.tr("Tiling"),icon:"grid_view"},
        {id:"scrolling",label:Tr.tr("Scrolling"),icon:"view_carousel"},
        {id:"stacking",label:Tr.tr("Stacking"),icon:"select_window"},
        {id:"canvas",label:Tr.tr("Infinite canvas"),icon:"gesture"}
    ]
    function reload(): void { backend.call(["config"], null, accept); }
    function accept(data: var): void { if (!data.error) config = data; }
    function select(id: string): void { backend.call(["mode",id],null,accept); }
    function save(key: string, value: var): void { backend.call(["save"],{[key]:value},accept); }
    function action(command: string): void { backend.call(["action",command],null,accept); }
    Component.onCompleted: {
        reload();
        if (!GlobalConfig.bar.layoutSwitcherConfigured) {
            if (!GlobalConfig.bar.entries.values.some(e=>e.id==="layoutSwitcher")) GlobalConfig.bar.entries.insert({id:"layoutSwitcher",enabled:true});
            GlobalConfig.bar.layoutSwitcherConfigured = true;
        }
    }
    FeatureBackend { id: backend; helper: "layout_controls.py" }
    FileView { path: `${Paths.config}/layouts.json`; printErrors:false;watchChanges:true;onFileChanged:root.reload() }
    IpcHandler { target:"layouts";function mode(value:string):void{root.select(value);}function state():string{return JSON.stringify({mode:root.mode,busy:root.busy,error:root.error,config:root.config});} }
}
