pragma Singleton

import QtQuick
import Quickshell
import Quickshell.Io

Singleton {
    id: root

    readonly property alias running: props.running
    readonly property alias paused: props.paused
    readonly property alias elapsed: props.elapsed
    readonly property alias state: props.state
    readonly property bool busy: state !== "idle" || startProc.running || controlProc.running
    readonly property bool controlBusy: controlProc.running || cancelRequested
    property int refCount: 0
    property bool cancelRequested: false
    property list<string> startArgs
    property string lastError: ""
    property string commandError: ""
    property var queriedState: ({running: false, paused: false, elapsed: 0, state: "idle"})

    function refresh(): void {
        if (!checkProc.running)
            checkProc.running = true;
    }

    function reconcile(): void {
        const current = root.queriedState;
        props.running = !!current.running;
        props.paused = props.running && !!current.paused;
        props.elapsed = props.running ? current.elapsed : 0;
        if (root.cancelRequested)
            props.state = "stopping";
        else if (props.running)
            props.state = props.paused ? "paused" : "recording";
        else if (current.state === "selecting" || current.state === "starting")
            props.state = current.state;
        else if (startProc.running)
            props.state = root.startArgs.includes("-r") || root.startArgs.includes("-sr") ? "selecting" : "starting";
        else
            props.state = "idle";
    }

    function start(extraArgs = []): void {
        if (root.busy)
            return;
        root.lastError = "";
        root.commandError = "";
        root.startArgs = extraArgs;
        props.state = extraArgs.includes("-r") || extraArgs.includes("-sr") ? "selecting" : "starting";
        startProc.exec(["hics", "record", ...extraArgs]);
    }

    function finishStop(): void {
        if (!controlProc.running)
            controlProc.exec(["hics", "record", "--stop"]);
    }

    function stop(): void {
        if (root.controlBusy)
            return;
        root.cancelRequested = true;
        props.state = "stopping";
        if (startProc.running)
            startProc.signal(15);
        else
            root.finishStop();
    }

    function togglePause(): void {
        if (!props.running || root.controlBusy)
            return;
        root.commandError = "";
        controlProc.exec(["hics", "record", "--pause"]);
    }

    PersistentProperties {
        id: props

        property bool running: false
        property bool paused: false
        property real elapsed: 0
        property string state: "idle"

        reloadableId: "recorder"
    }

    Binding {
        target: Time
        property: "recordingActive"
        value: props.running && !props.paused
    }

    Process {
        id: checkProc

        running: true
        command: ["hics", "record", "--status"]
        stdout: StdioCollector {
            onStreamFinished: {
                try { root.queriedState = JSON.parse(text); }
                catch (error) { root.queriedState = {running: false, paused: false, elapsed: 0, state: "idle"}; }
            }
        }
        onExited: code => { // qmllint disable signal-handler-parameters
            if (code !== 0)
                root.queriedState = {running: false, paused: false, elapsed: 0, state: "idle"};
            root.reconcile();
        }
    }

    Process {
        id: startProc

        stderr: StdioCollector {
            onStreamFinished: root.commandError = text.trim()
        }
        onStarted: {
            if (root.cancelRequested)
                startProc.signal(15);
        }
        onExited: code => { // qmllint disable signal-handler-parameters
            if (root.cancelRequested)
                root.finishStop();
            else if (code !== 0)
                root.lastError = root.commandError;
            root.refresh();
        }
    }

    Process {
        id: controlProc

        stderr: StdioCollector {
            onStreamFinished: root.commandError = text.trim()
        }
        onExited: code => { // qmllint disable signal-handler-parameters
            if (code !== 0)
                root.lastError = root.commandError;
            root.cancelRequested = false;
            root.refresh();
        }
    }

    FileView {
        path: `${Quickshell.env("XDG_STATE_HOME") || Quickshell.env("HOME") + "/.local/state"}/hics/record/status.json`
        printErrors: false
        watchChanges: true
        onFileChanged: { reload(); root.refresh(); }
    }

    FileView {
        path: `${Quickshell.env("XDG_STATE_HOME") || Quickshell.env("HOME") + "/.local/state"}/hics/record/start.json`
        printErrors: false
        watchChanges: true
        onFileChanged: { reload(); root.refresh(); }
    }

    Timer {
        interval: 500
        running: root.refCount > 0 || root.busy
        repeat: true
        triggeredOnStart: true
        onTriggered: root.refresh()
    }

    Connections {
        function onSecondsChanged(): void {
            props.elapsed++;
        }

        enabled: props.running && !props.paused
        target: Time // qmllint disable incompatible-type
    }
}
