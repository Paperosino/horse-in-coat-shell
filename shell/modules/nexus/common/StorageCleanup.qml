pragma ComponentBehavior: Bound
import QtQuick
import Hyprstack.Config
import Hyprstack.I18n
import Hyprstack.Services
import qs.services
SettingsCard {
 id:root
 property string confirmation:""
 property var backend
 InfoRow {visible:root.backend?.busy??false;first:true;last:true;label:Tr.tr("System cleanup");value:Tr.tr("Authorizing and scheduling maintenance") }
 title:Tr.tr("Free up space")
 icon:"cleaning_services"
 Component.onCompleted:DesktopConveniences.inspectCleanup()
 InfoRow {first:true;last:true;label:Tr.tr("Reclaimable files");value:Tr.tr("Trash: %1 · Thumbnails: %2").arg(Math.round((DesktopConveniences.cleanup.trash??0)/1048576)+" MiB").arg(Math.round((DesktopConveniences.cleanup.thumbnails??0)/1048576)+" MiB")}
 InfoRow {first:true;last:true;label:Tr.tr("Estimate");value:Tr.tr("Trash size covers the home volume; other mounted volumes are not included") }
 RowButton {text:Tr.tr("Open Trash");icon:"delete";onClicked:DesktopConveniences.launch("trash")}
 RowButton {text:root.confirmation==="trash"?Tr.tr("Confirm: permanently empty Trash"):Tr.tr("Empty Trash");subtext:Tr.tr("Permanently removes all trashed items, including mounted volumes");icon:"delete_forever";disabled:DesktopConveniences.busy;onClicked:{if(root.confirmation==="trash"){DesktopConveniences.clean("trash",0);root.confirmation="";}else root.confirmation="trash";}}
 RowButton {text:root.confirmation==="thumbnails"?Tr.tr("Confirm: remove old thumbnails"):Tr.tr("Remove old thumbnails");subtext:Tr.tr("Thumbnails are regenerated when needed; original files are kept");icon:"image";disabled:DesktopConveniences.busy;onClicked:{if(root.confirmation==="thumbnails"){DesktopConveniences.clean("thumbnails",GlobalConfig.general.maintenance.thumbnailRetentionDays);root.confirmation="";}else root.confirmation="thumbnails";}}
 ToggleRow {text:Tr.tr("Automatically remove old thumbnails");checked:GlobalConfig.general.maintenance.automaticThumbnailCleanup;onToggled:GlobalConfig.general.maintenance.automaticThumbnailCleanup=checked}
 StepperRow {label:Tr.tr("Keep thumbnails for (days)");value:GlobalConfig.general.maintenance.thumbnailRetentionDays;from:1;to:365;stepSize:1;onMoved:v=>GlobalConfig.general.maintenance.thumbnailRetentionDays=v}
 RowButton {text:root.confirmation==="packages"?Tr.tr("Confirm: clean package cache"):Tr.tr("Clean package cache");subtext:Tr.tr("Keeps the three most recent cached versions; authorization is required");icon:"inventory_2";disabled:(root.backend?.busy??true)||!(root.backend?.state.packageCleanupAvailable??false);onClicked:{if(root.confirmation==="packages"){root.backend.apply("clean-packages",{});root.confirmation="";}else root.confirmation="packages";}}
 RowButton {text:root.confirmation==="coredumps"?Tr.tr("Confirm: remove expired crash dumps"):Tr.tr("Remove expired crash dumps");subtext:Tr.tr("Uses the system retention policy; recent diagnostic dumps are kept");icon:"bug_report";disabled:root.backend?.busy??true;onClicked:{if(root.confirmation==="coredumps"){root.backend.apply("clean-coredumps",{});root.confirmation="";}else root.confirmation="coredumps";}}
 ToggleRow {text:Tr.tr("Automatically clean the package cache");subtext:Tr.tr("Uses the system paccache timer and its retention settings");checked:root.backend?.state.automaticPackageCleanup??false;enabled:!(root.backend?.busy??true)&&(root.backend?.state.packageCleanupAvailable??false);onToggled:root.backend.apply("automatic-package-cleanup",{enabled:checked})}
 Repeater {
    model:["packages","coredumps"]
    InfoRow {required property var modelData;first:true;last:true;label:modelData==="packages"?Tr.tr("Package cache cleanup"):Tr.tr("Crash dump cleanup");value:{const job=root.backend?.state.cleanupJobs?.[modelData];return job?.active?Tr.tr("Running"):job?.result==="success"?Tr.tr("Finished"):job?.result?Tr.tr("Failed"):Tr.tr("Not started");}}
 }
 FeatureError {error:root.backend?.message??""}
 RowButton {text:Tr.tr("Refresh space estimate");icon:"refresh";disabled:DesktopConveniences.busy;onClicked:DesktopConveniences.inspectCleanup()}
 RowButton {visible:root.confirmation!=="";text:Tr.tr("Cancel");icon:"close";onClicked:root.confirmation=""}
 FeatureError {error:DesktopConveniences.error}
}
