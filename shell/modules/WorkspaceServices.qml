pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Io
import Hyprstack.Config
import Hyprstack.I18n
import Hyprstack.Services
import qs.components
import qs.components.controls
import qs.modules.nexus.common
import qs.services

Scope {
    id:root
    property bool locked:false
    onLockedChanged:ClipboardHistory.setLocked(locked)
    Component.onCompleted:{ClipboardHistory.setLocked(locked);ShortcutEditor.refresh();WorkspaceSession.refresh();startup.running=true}
    Process {id:startup;command:["hics-workspace","startup"];onExited:WorkspaceSession.refresh()}
    Timer {interval:WorkspaceSession.settings.interval*1000;repeat:true;running:WorkspaceSession.settings.enabled&&WorkspaceSession.settings.autosave&&!WorkspaceSession.busy&&!WorkspaceSession.startupPending;onTriggered:WorkspaceSession.capture(Tr.tr("Automatic checkpoint"),true)}
    Timer {interval:5000;repeat:true;running:true;onTriggered:if(!WorkspaceSession.busy)WorkspaceSession.refresh()}
    Connections {target:Hypr;function onConfigReloaded():void {ShortcutEditor.refresh()}}
    FloatingWindow {
        id:prompt
        visible:WorkspaceSession.startupPending&&!root.locked
        title:Tr.tr("Restore your workspace")
        implicitWidth:500*Tokens.scale;implicitHeight:content.implicitHeight+40
        color:Colours.palette.m3surface
        onClosed:WorkspaceSession.dismissStartup()
        ColumnLayout {
            id:content;anchors.left:parent.left;anchors.right:parent.right;anchors.top:parent.top;anchors.margins:20;spacing:Tokens.spacing.medium
            SettingsCard {
                title:Tr.tr("Welcome back");description:Tr.tr("Your saved applications can be restored now, or you can start with an empty workspace.");icon:"restore"
                FeatureError {error:WorkspaceSession.error}
                RowButton {text:Tr.tr("Restore saved session");icon:"restore";disabled:WorkspaceSession.busy;onClicked:WorkspaceSession.restore(WorkspaceSession.settings.startupSnapshot??"automatic",[])}
                RowButton {text:Tr.tr("Start fresh");icon:"add";disabled:WorkspaceSession.busy;onClicked:WorkspaceSession.dismissStartup()}
            }
        }
    }
}
