pragma Singleton
pragma ComponentBehavior: Bound

import QtQuick
import Quickshell
import Quickshell.Io
import qs.services
import qs.utils

Singleton {
    id: root

    readonly property string helperPath: Paths.toLocalFile(Qt.resolvedUrl("../assets/clipboard_helper.py"))

    property var entries: []
    property bool busy: false
    property string query: ""
    property string lastError: ""
    property var deleteQueue: []

    readonly property var filteredEntries: {
        const q = query.trim().toLowerCase();
        if (!q) return entries;
        return entries.filter(e => (e.text || "").toLowerCase().includes(q));
    }

    function reload(): void {
        if (busy) return;
        busy = true;
        listProc.running = true;
    }

    function copy(entry: var): void {
        if (!entry || !entry.raw) return;
        const b64 = Qt.btoa(entry.raw);
        copyProc.command = ["python3", root.helperPath, "copy", "--b64", b64];
        copyProc.running = true;
        closeDrawer();
    }

    function deleteEntry(entry: var): void {
        if (!entry || !entry.raw) return;
        // Optimistic UI update: instantly remove from list
        root.entries = root.entries.filter(e => e.id !== entry.id);
        deleteQueue.push(entry.raw);
        processDeleteQueue();
    }

    function processDeleteQueue(): void {
        if (deleteProc.running || deleteQueue.length === 0) return;
        const raw = deleteQueue.shift();
        const b64 = Qt.btoa(raw);
        deleteProc.command = ["python3", root.helperPath, "delete", "--b64", b64];
        deleteProc.running = true;
    }

    function clearAll(): void {
        root.entries = [];
        wipeProc.running = true;
    }

    function decodeEntry(rawText: string, callback: var): void {
        decodeProc.callback = callback;
        const b64 = Qt.btoa(rawText);
        decodeProc.command = ["python3", root.helperPath, "decode", "--b64", b64];
        decodeProc.running = true;
    }

    function saveEditedText(oldRaw: string, newText: string, callback: var): void {
        editProc.callback = callback;
        const rawB64 = Qt.btoa(oldRaw);
        const textB64 = Qt.btoa(newText);
        editProc.command = ["python3", root.helperPath, "edit", "--b64-raw", rawB64, "--b64-text", textB64];
        editProc.running = true;
    }

    function closeDrawer(): void {
        for (const s of ShellState.states.instances) {
            s.clipboard = false;
        }
    }

    Process {
        id: listProc
        command: ["python3", root.helperPath, "list"]
        stdout: StdioCollector {
            onStreamFinished: {
                root.busy = false;
                try {
                    const parsed = JSON.parse(text);
                    if (Array.isArray(parsed)) {
                        root.entries = parsed;
                    }
                } catch (e) {
                    root.lastError = "Failed to parse clipboard list: " + e;
                }
            }
        }
        onExited: (code, status) => {
            root.busy = false;
            if (code !== 0) root.lastError = "Failed to list clipboard history";
        }
    }

    Process {
        id: copyProc
        command: ["python3", root.helperPath, "copy"]
    }

    Process {
        id: deleteProc
        command: ["python3", root.helperPath, "delete"]
        onExited: {
            if (deleteQueue.length > 0) {
                processDeleteQueue();
            } else {
                root.reload();
            }
        }
    }

    Process {
        id: wipeProc
        command: ["python3", root.helperPath, "wipe"]
        onExited: root.reload()
    }

    Process {
        id: decodeProc
        property var callback: null
        command: ["python3", root.helperPath, "decode"]
        stdout: StdioCollector {
            id: decodeCollector
            onStreamFinished: {
                if (decodeProc.callback) {
                    decodeProc.callback(text);
                    decodeProc.callback = null;
                }
            }
        }
        onExited: (code, status) => {
            if (decodeProc.callback) {
                decodeProc.callback(decodeCollector.text);
                decodeProc.callback = null;
            }
        }
    }

    Process {
        id: editProc
        property var callback: null
        command: ["python3", root.helperPath, "edit"]
        stdout: StdioCollector {
            id: editCollector
            onStreamFinished: {
                if (editProc.callback) {
                    editProc.callback(true);
                    editProc.callback = null;
                }
            }
        }
        onExited: (code, status) => {
            if (editProc.callback) {
                editProc.callback(true);
                editProc.callback = null;
            }
            root.reload();
        }
    }
}
