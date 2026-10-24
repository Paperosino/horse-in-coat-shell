pragma ComponentBehavior: Bound
import QtQuick
import Quickshell.Io
import qs.utils

Item {
    id: root
    property string helper
    property var coalescePatches: []
    property string executable
    property string error: ""
    readonly property bool busy: current !== null || proc.running || queue.length > 0
    property var queue: []
    property var current: null
    visible: false
    function call(args: var, payload = null, callback = null): void {
        // Merge adjacent pending reads only. Never merge across a mutation or
        // reuse the in-flight result: a file-change signal may make it stale.
        const last = queue.length ? queue[queue.length - 1] : null;
        const readOnly = payload === null && ["list", "config", "library"].includes(args[0]);
        const sameArgs = last && JSON.stringify(last.args) === JSON.stringify(args);
        const mergePatch = sameArgs && coalescePatches.includes(args[0]) && payload !== null && last.payload !== null
            && typeof payload === "object" && typeof last.payload === "object" && !Array.isArray(payload) && !Array.isArray(last.payload);
        if (mergePatch) {
            last.payload = Object.assign({}, last.payload, payload);
            if (callback) last.callbacks.push(callback);
        } else if (readOnly && last?.payload === null && sameArgs) {
            if (callback) last.callbacks.push(callback);
        } else {
            queue = [...queue, {args: args, payload: payload, callbacks: callback ? [callback] : []}];
        }
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
            for (const callback of completed.callbacks) callback(result);
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
