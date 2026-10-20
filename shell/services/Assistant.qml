pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Io
import qs.components
import qs.modules.nexus
import qs.utils

Singleton {
    id: root
    property var config: ({provider: "ollama", endpoint: "http://127.0.0.1:11434", model: "", rememberHistory: true})
    property var messages: []
    property var models: []
    property string response: ""
    property string chatError: ""
    readonly property string error: chatError || backend.error
    readonly property bool busy: chat.running
    readonly property bool settingsBusy: backend.busy
    readonly property string helper: Paths.toLocalFile(Qt.resolvedUrl("../assets/assistant_backend.py"))
    function configure(value: var): void { backend.call(["save"], value, d => { if (!d.error) config = d; }); }
    function reloadModels(): void { backend.call(["models"], null, d => { if (!d.error) models = d.models; }); }
    function clear(): void { if (busy) return; backend.call(["clear"], null, d => { messages = []; response = ""; chatError = ""; }); }
    function forgetKey(): void { backend.call(["forget-key"], null, d => { if (!d.error) config = d; }); }
    function send(text: string): void {
        if (busy || settingsBusy || !text.trim()) return;
        chatError = ""; response = "";
        messages = [...messages, {role: "user", content: text.trim()}];
        chat.stdinEnabled = true; chat.running = true;
    }
    function stop(): void { chat.running = false; }
    Component.onCompleted: {
        backend.call(["config"], null, d => { if (!d.error) config = d; });
        backend.call(["history"], null, d => { if (!d.error) messages = d.messages; });
    }
    IpcHandler { target: "assistant"; function open(): void { WindowFactory.openPage("assistant"); } }
    FeatureBackend { id: backend; helper: "assistant_backend.py" }
    Process {
        id: chat
        command: ["python3", "-u", root.helper, "chat"]
        onStarted: { write(JSON.stringify({messages: root.messages})); stdinEnabled = false; }
        stdout: SplitParser {
            onRead: data => {
                try {
                    const event = JSON.parse(data);
                    if (event.error) root.chatError = event.error;
                    if (event.delta) root.response += event.delta;
                } catch (e) { root.chatError = "Unable to read assistant response"; }
            }
        }
        stderr: StdioCollector { id: stderr }
        onExited: (code, status) => {
            if (root.response) root.messages = [...root.messages, {role: "assistant", content: root.response}];
            root.response = "";
            if (code !== 0 && !root.chatError && stderr.text) root.chatError = stderr.text.trim().slice(0, 300);
        }
    }
}
