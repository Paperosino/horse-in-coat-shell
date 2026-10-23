pragma ComponentBehavior: Bound
import QtQuick
import Quickshell.Io
import qs.utils

Item {
    id: root
    property string helper
    property string executable
    property string error: ""
    readonly property bool busy: current !== null || proc.running || queue.length > 0
    property var queue: []
    property var current: null
    visible: false
    function call(args: var, payload = null, callback = null): void {
        queue = [...queue, {args: args, payload: payload, callback: callback}];
        Qt.callLater(next);
    }
    function next(): void {
        if (current !== null || proc.running || !queue.length) return;
        current = queue[0]; queue = queue.slice(1); error = "";
        proc.command = executable ? [executable, ...current.args] : ["python3", Paths.toLocalFile(Qt.resolvedUrl("../assets/" + helper)), ...current.args];
        proc.stdinEnabled = current.payload !== null;
        proc.running = true;
    }
    function complete(result: var): void {
        const completed = current;
        if (!completed) return;
        current = null;
        error = result?.error || "";
        try {
            if (completed.callback) completed.callback(result);
        } finally {
            Qt.callLater(next);
        }
    }
    // FailedToStart has no finished signal in QProcess. Defer until after
    // ordinary exited delivery, so the same request is completed exactly once.
    Timer {
        id: startupFailure
        interval: 0
        onTriggered: if (root.current !== null && !proc.running)
            root.complete({error: "Unable to start feature helper"});
    }
    Process {
        id: proc
        stdout: StdioCollector { id: out }
        stderr: StdioCollector { id: err }
        onRunningChanged: if (!running && root.current !== null) startupFailure.restart()
        onStarted: {
            if (root.current.payload !== null) write(JSON.stringify(root.current.payload));
            stdinEnabled = false;
        }
        onExited: (code, status) => {
            startupFailure.stop();
            let result;
            try { result = JSON.parse(out.text || "{}"); }
            catch (e) { result = {error: err.text.trim() || "Unable to read feature response"}; }
            if (code !== 0 || status !== 0)
                result = {error: result?.error || err.text.trim() || "Operation failed"};
            root.complete(result ?? {});
        }
    }
}
