pragma Singleton
pragma ComponentBehavior: Bound
import QtQuick
import Quickshell
import Hyprstack.Config
import Hyprstack.Services
Singleton {
    id:root
    readonly property var config:GlobalConfig.background.desktopIcons
    readonly property bool enabled:config.enabled
    property string error:""
    Binding {target:DesktopFiles;property:"active";value:root.enabled}
    Binding {target:DesktopFiles;property:"showHidden";value:root.config.showHidden}
    function onScreen(screen):bool {return enabled && screen?.name===(Quickshell.screens.some(output=>output.name===config.output)?config.output:Quickshell.screens[0]?.name);}
    function openFolder():void {
        DesktopJobs.request("integration.desktop",{action:"ensure"},result=>{if(result.error)root.error=result.error;else DesktopFiles.open(DesktopFiles.directoryUrl);},root);
    }
    function operation(action:string,extra:var):void {
        const args=Object.assign({action},extra);error="";
        DesktopJobs.request("integration.desktop",args,result=>{root.error=result.error??"";DesktopFiles.refresh();},root);
    }
    function paste():void {
        const clip=DesktopFiles.clipboardFiles();if(!clip.sources?.length)return;
        if(clip.cut){
            error="";
            DesktopJobs.request("integration.desktop",{action:"move",sources:clip.sources},result=>{root.error=result.error??"";if(!result.error)DesktopFiles.releaseCut(clip.sources);DesktopFiles.refresh();},root);
        }
        else copyToDesktop(clip.sources);
    }
    function copyToDesktop(sources:var):void {
        error="";
        if(!DesktopFiles.directory)return;
        // Ensure a missing Desktop folder exists before using the common copier.
        DesktopJobs.request("integration.desktop",{action:"ensure"},created=>{
            if(created.error){root.error=created.error;return;}
            DesktopJobs.request("transfer.copy",{sources,target:DesktopFiles.directory},result=>{root.error=result.error??"";DesktopFiles.refresh();},root);
        },root);
    }
}
