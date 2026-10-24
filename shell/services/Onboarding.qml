pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Io
import qs.utils
import Hyprstack.Config
import Hyprstack.I18n
import qs.components
Singleton {
 id:root
 property string screenName:""
 readonly property string primaryScreen:Quickshell.screens.find(s=>s.name===screenName)?.name??Quickshell.screens[0]?.name??""
 property bool running:false
 onRunningChanged:if(running){screenName=Hypr.focusedMonitor?.name??"";Overview.close(false);WindowSwitcher.close();for(const screen of Quickshell.screens){const state=ShellState.forScreen(screen);for(const key of ["launcher","dashboard","sidebar","session","clipboard","utilities","osd"])state[key]=false;}}
 property bool initialized:false
 property int step:0
 property var data:({settings:{showDemos:true},wallpapers:[]})
 property string guardError:""
 readonly property string error:backend.error||downloads.error||Tr.tr(guardError)
 readonly property bool downloading:downloads.busy
 readonly property var steps:[
  {id:"welcome",title:Tr.tr("Welcome to hics"),icon:"waving_hand",demo:"stacking",description:Tr.tr("A desktop that follows your way of working. Discover the dock, the panel and four ways to arrange your windows.")},
  {id:"locale",title:Tr.tr("Speak your language"),icon:"language",demo:"keyboard",description:Tr.tr("Choose the shell language and the system locale for language, dates and numbers. Existing applications pick up a new system locale after signing in again.")},
  {id:"keyboard",title:Tr.tr("All your keyboard layouts"),icon:"keyboard",demo:"keyboard",description:Tr.tr("Add every layout you use, arrange their order and choose a switching shortcut. These are the same settings used throughout the desktop.")},
  {id:"displays",title:Tr.tr("Make room on your screens"),icon:"monitor",demo:"displays",description:Tr.tr("Arrange screens, choose their native refresh rates and save profiles. Every change has a confirmation timer and an independent rollback guard.")},
  {id:"windows",title:Tr.tr("Choose how windows live"),icon:"view_quilt",demo:LayoutModes.mode,description:Tr.tr("Stack familiar windows, tile them, scroll through columns or explore an infinite canvas. You can switch modes later from the panel.")},
  {id:"theme",title:Tr.tr("Make the desktop yours"),icon:"palette",demo:"themes",description:Tr.tr("One palette connects the shell and GTK and Qt applications. Complete desktop profiles can also preserve panels, typography and effects.")},
  {id:"wallpapers",title:Tr.tr("A view you enjoy"),icon:"wallpaper",demo:"themes",description:Tr.tr("Explore a curated collection of light and dark wallpapers. The original artwork, its author metadata and license are kept alongside the images.")},
  {id:"storage",title:Tr.tr("Your disks and memory"),icon:"storage",demo:"storage",description:Tr.tr("Review volumes, safe removal and memory compression. Disk changes are optional; administrative actions ask for authorization.")},
  {id:"features",title:Tr.tr("Small tools, less friction"),icon:"auto_awesome",demo:"features",description:Tr.tr("Clipboard history, shortcuts, projects and recoverable settings are built in. Extensions add more, and a safe startup helps isolate failures.")},
  {id:"ready",title:Tr.tr("Your desktop is ready"),icon:"check_circle",demo:"canvas",description:Tr.tr("Everything remains available in Settings. Replay this guide whenever you want, or start working now.")}
 ]
 function accept(d:var):void {
  if(d.error||!d.settings)return;data=d;
  if(!initialized){initialized=true;step=d.settings.step??0;if(Quickshell.env("HICS_NO_ONBOARDING")!=="1"&&d.settings.autoShow&&["new","in-progress"].includes(d.settings.state))running=true;}
 }
 function open(start=0):void {step=start;running=true;backend.call(["open"],{step:step},accept);}
 function go(index:int):void {step=Math.max(0,Math.min(steps.length-1,index));backend.call(["configure"],{step:step},accept);}
 function skip():void {if(DisplayProfiles.pending)DisplayProfiles.revert();if(DesktopConfiguration.pending)DesktopConfiguration.revert();running=false;backend.call(["skip"],{},accept);}
 function finish():void {running=false;backend.call(["finish"],{},accept);}
 function configure(value:var):void {backend.call(["configure"],value,accept);}
 function downloadWallpapers():void {if(!downloading)downloads.call(["wallpapers"],null,accept);}
 function poster(id:string):url {const language=Tr.language.startsWith("ru")?"ru_RU":"en_US";return Qt.resolvedUrl("../assets/tour/"+language+"/"+id+".jpg");}
 function video(id:string):url {const language=Tr.language.startsWith("ru")?"ru_RU":"en_US";return Qt.resolvedUrl("../assets/tour/"+language+"/"+id+".mp4");}
 Process {
  command:["python3",Paths.toLocalFile(Qt.resolvedUrl("../assets/onboarding_guard.py"))]
  running:root.running;stdinEnabled:true
  stdout:StdioCollector {}
  stderr:StdioCollector {id:guardStderr}
  onStarted:root.guardError=""
  onExited:if(root.running)root.guardError=guardStderr.text.trim()||"Unable to isolate desktop shortcuts"
 }
 function demo(id:string):url {const language=Tr.language.startsWith("ru")?"ru_RU":"en_US";return Qt.resolvedUrl("../assets/tour/"+language+"/"+id+".gif");}
 Component.onCompleted:backend.call(["status"],null,accept)
 FeatureBackend {id:backend;helper:"onboarding_manager.py"}
 FeatureBackend {id:downloads;helper:"onboarding_manager.py"}
}
