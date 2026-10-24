pragma Singleton
pragma ComponentBehavior: Bound
import QtQuick
import Quickshell
import Hyprstack.Services
import qs.services
Singleton {
    id:root
    readonly property var entries:ClipboardHistory.entries
    readonly property bool busy:ClipboardHistory.busy
    property string query:""
    readonly property string lastError:ClipboardHistory.error
    readonly property var filteredEntries:entries.filter(e=>!query.trim()||[e.text,e.application,e.mime].join(" ").toLowerCase().includes(query.trim().toLowerCase()))
    function reload():void {ClipboardHistory.refresh()}
    function copy(entry):void {if(entry?.id){ClipboardHistory.copy(entry.id);if(!ClipboardHistory.error)closeDrawer()}}
    function deleteEntry(entry):void {if(entry?.id)ClipboardHistory.remove(entry.id)}
    function pin(entry):void {if(entry?.id)ClipboardHistory.pin(entry.id)}
    function clearAll():void {ClipboardHistory.clear(true)}
    function decodeEntry(id,callback):void {callback(ClipboardHistory.decode(id))}
    function saveEditedText(id,text,callback):void {ClipboardHistory.edit(id,text);callback(!ClipboardHistory.error)}
    function closeDrawer():void {for(const screen of Quickshell.screens){const s=ShellState.forScreen(screen);if(s)s.clipboard=false}}
}
