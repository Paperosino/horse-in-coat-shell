pragma Singleton
pragma ComponentBehavior: Bound
import QtQuick
import Quickshell
import Hyprstack.Config
import Hyprstack.Services
import Hyprstack.I18n
Singleton {
 id:root
 property int openCount:0
 property var rows:[]
 property var cache:({})
 readonly property var jobs:DesktopJobs.jobs
 readonly property var active:jobs.filter(job=>!job.finished)
 readonly property var unseen:jobs.filter(job=>job.finished&&!job.seen)
 readonly property int errors:unseen.filter(job=>job.phase==="failed"||job.phase==="interrupted").length
 readonly property bool visible:DesktopJobs.available&&GlobalConfig.utilities.operations.autoShow&&(openCount>0||active.length>0||unseen.some(job=>GlobalConfig.utilities.operations.retainErrors||!["failed","interrupted"].includes(job.phase)))
 readonly property real progress:active.length&&active.every(job=>job.progress>=0)?active.reduce((total,job)=>total+job.progress,0)/active.length:-1
 readonly property int count:active.length||unseen.length
 readonly property var names:({"backup.run":Tr.tr("Personal file backup"),"backup.init":Tr.tr("Create backup repository"),"backup.restore":Tr.tr("Restore files"),"backup.check":Tr.tr("Check backup integrity"),"backup.snapshots":Tr.tr("Read backup snapshots"),"backup.files":Tr.tr("Browse backup files"),"maintenance.disk":Tr.tr("Disk maintenance"),"search.index":Tr.tr("Index documents"),"diagnostics.check":Tr.tr("Desktop checks"),"apps.remove":Tr.tr("Remove application"),"transfer.copy":Tr.tr("Copy files"),"transfer.send":Tr.tr("Send files"),"maintenance.cleanup":Tr.tr("Disk cleanup"),"update.install":Tr.tr("System update")})
 function title(job):string {return names[job.operation]??Tr.tr("Background operation");}
 function acknowledge():void {DesktopJobs.acknowledge();}
 function sync():void {
  const next={},values=[];
  for(const job of jobs){const row=cache[job.id]??record.createObject(root);if(!row.data.id||row.data.phase!==job.phase||row.data.progress!==job.progress||row.data.seen!==job.seen||row.data.finished!==job.finished||row.data.error!==job.error||row.data.cancellable!==job.cancellable||row.data.retryable!==job.retryable)row.data=job;next[job.id]=row;values.push(row);}
  for(const key of Object.keys(cache))if(!next[key])cache[key].destroy();
  cache=next;rows=values;

 }
 Component {id:record;QtObject {property var data:({})}}
 Connections {target:DesktopJobs;function onChanged():void {root.sync();}}
 Component.onCompleted:sync()
 Timer {
  id:linger;interval:1000;repeat:true;running:root.unseen.some(job=>!["failed","interrupted"].includes(job.phase)||!GlobalConfig.utilities.operations.retainErrors)
  onTriggered:{for(const job of root.unseen)if((!["failed","interrupted"].includes(job.phase)||!GlobalConfig.utilities.operations.retainErrors)&&Date.now()/1000-job.finished>=Math.max(1,Math.min(300,GlobalConfig.utilities.operations.completedSeconds)))DesktopJobs.acknowledge(job.id)}
 }
}
