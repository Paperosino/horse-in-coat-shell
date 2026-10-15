pragma Singleton

import QtQuick
import Quickshell
import Quickshell.Io

Singleton {
    id: root

    readonly property alias running: props.running
    readonly property alias paused: props.paused
    readonly property alias elapsed: props.elapsed
    property int refCount: 0
    property bool needsStart
    property list<string> startArgs
    property bool needsStop
    property bool needsPause
    property var queriedState: ({running: false, paused: false, elapsed: 0})

    function start(extraArgs = []): void {
        needsStart = true;
        startArgs = extraArgs;
        checkProc.running = true;
    }

    function stop(): void {
        needsStop = true;
        checkProc.running = true;
    }

    function togglePause(): void {
        needsPause = true;
        checkProc.running = true;
    }

    PersistentProperties {
        id: props

        property bool running: false
        property bool paused: false
        property real elapsed: 0 // Might get too large for int

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
        command: ["hyprstack", "record", "--status"]
        stdout: StdioCollector {
            onStreamFinished: {
                try { root.queriedState = JSON.parse(text); }
                catch (error) { root.queriedState = {running: false, paused: false, elapsed: 0}; }
            }
        }
        onExited: code => { // qmllint disable signal-handler-parameters
            const running = code === 0 && root.queriedState.running;

            if (running && root.needsStop) {
                commandProc.exec(["hyprstack", "record"]);
                props.running = false;
                props.paused = false;
            } else if (running && root.needsPause) {
                commandProc.exec(["hyprstack", "record", "-p"]);
                props.paused = !props.paused;
            } else if (!running && root.needsStart) {
                commandProc.exec(["hyprstack", "record", ...root.startArgs]);
                props.running = true;
                props.paused = root.queriedState.paused;
                props.elapsed = root.queriedState.elapsed;
            } else if (!commandProc.running) {
                // The recording was started/stopped outside the shell (e.g. via
                // keybind), or our command finished without reaching the optimistic state
                props.running = running;
                props.paused = running && root.queriedState.paused;
                props.elapsed = running ? root.queriedState.elapsed : 0;
            }

            root.needsStart = false;
            root.needsStop = false;
            root.needsPause = false;
        }
    }

    Process {
        id: commandProc

        // Reconcile with our recorder, including cancelled region selection.
        onExited: checkProc.running = true // qmllint disable signal-handler-parameters
    }

    FileView {
        path: `${Quickshell.env("XDG_STATE_HOME") || Quickshell.env("HOME") + "/.local/state"}/hyprstack/record/status.json`
        printErrors: false
        watchChanges: true
        onFileChanged: { reload(); checkProc.running = true; }
    }

    // Only poll while something is showing the state, i.e. the utilities drawer is open
    Timer {
        interval: 1000
        running: root.refCount > 0
        repeat: true
        triggeredOnStart: true

        onTriggered: checkProc.running = true
    }

    Connections {
        function onSecondsChanged(): void {
            props.elapsed++;
        }

        enabled: props.running && !props.paused
        target: Time // qmllint disable incompatible-type
    }
}
