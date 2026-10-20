pragma ComponentBehavior: Bound
import QtQuick
import Quickshell.Io
import qs.utils

Item {
    id: root
    property string helper
    property string executable
    property string error: ""
    readonly property bool busy: proc.running || queue.length > 0
    property var queue: []
    property var current: null
    visible: false
    function call(args: var, payload = null, callback = null): void {
        queue = [...queue, {args: args, payload: payload, callback: callback}];
        Qt.callLater(next);
    }
    function next(): void {
        if (proc.running || !queue.length) return;
        current = queue[0]; queue = queue.slice(1); error = "";
        proc.command = executable ? [executable, ...current.args] : ["python3", Paths.toLocalFile(Qt.resolvedUrl("../assets/" + helper)), ...current.args];
        proc.stdinEnabled = current.payload !== null;
        proc.running = true;
    }
    Process {
        id: proc
        stdout: StdioCollector { id: out }
        stderr: StdioCollector { id: err }
        onStarted: {
            if (root.current.payload !== null) write(JSON.stringify(root.current.payload));
            stdinEnabled = false;
        }
        onExited: (code, status) => {
            let result;
            try { result = JSON.parse(out.text || "{}"); }
            catch (e) { result = {error: err.text.trim() || "Unable to read feature response"}; }
            if (result.error || code !== 0) root.error = result.error || err.text.trim() || "Operation failed";
            if (root.current?.callback) root.current.callback(result);
            root.current = null;
            Qt.callLater(root.next);
        }
    }
}
