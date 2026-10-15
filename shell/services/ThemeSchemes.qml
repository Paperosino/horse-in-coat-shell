pragma Singleton
pragma ComponentBehavior: Bound

import QtQuick
import Quickshell
import Quickshell.Io
import Hyprstack.I18n
import qs.services
import qs.utils

Singleton {
    id: root

    property var themes: []
    property string error
    property var catalogueErrors: []
    readonly property bool busy: mutation.running
    readonly property string helper: Paths.toLocalFile(Qt.resolvedUrl("../assets/theme_manager.py"))
    readonly property var currentTheme: themes.find(t => t.id === Colours.scheme || t.aliases.includes(Colours.scheme)) ?? null
    readonly property var currentVariant: currentTheme?.variants.find(v => v.mode === (Colours.currentLight ? "light" : "dark")
        && v.accent === Colours.accent) ?? null
    property string payload
    property string operation
    property string requestedMode: "dark"
    property var result: ({})

    function reload(): void {
        if (!catalogue.running)
            catalogue.running = true;
    }

    function run(args: list<string>, kind: string, data: string): void {
        if (busy)
            return;
        error = "";
        operation = kind;
        payload = data;
        result = {};
        mutation.command = ["python3", helper, ...args];
        mutation.stdinEnabled = data.length > 0;
        mutation.running = true;
    }

    function apply(id: string, mode: string, accent = ""): void {
        run(["apply", id, mode, ...(accent ? ["--accent", accent] : [])], "apply", "");
    }

    function setMode(mode: string): void {
        run(["mode", mode], "apply", "");
    }

    function importFile(path: string, mode: string): void {
        requestedMode = mode;
        run(["import", path, "--mode", mode], "import", "");
    }

    function create(name: string, modes: var, mode: string): void {
        requestedMode = mode;
        run(["create"], "import", JSON.stringify({name, modes}));
    }

    Component.onCompleted: {
        reload();
        run(["refresh"], "refresh", "");
    }

    Process {
        id: catalogue

        command: ["python3", root.helper, "list"]
        stdout: StdioCollector {
            onStreamFinished: {
                try {
                    const data = JSON.parse(text);
                    if (data.error) {
                        root.error = data.error;
                    } else {
                        root.themes = data.themes;
                        root.catalogueErrors = data.errors;
                    }
                } catch (err) {
                    root.error = Tr.tr("Unable to read colour schemes: %1").arg(err);
                }
            }
        }
    }

    Process {
        id: mutation

        onStarted: {
            if (root.payload)
                mutation.write(root.payload);
            mutation.stdinEnabled = false;
        }
        stdout: StdioCollector {
            onStreamFinished: {
                try {
                    root.result = JSON.parse(text);
                    if (root.result.error)
                        root.error = root.result.error;
                } catch (err) {
                    root.error = Tr.tr("Unable to change colour scheme: %1").arg(err);
                }
            }
        }
        onExited: (exitCode, exitStatus) => {
            if (exitCode !== 0 || exitStatus !== 0) {
                if (!root.error)
                    root.error = Tr.tr("Unable to change colour scheme");
                return;
            }
            if (root.operation === "import" || (root.operation === "apply" && root.result.name?.startsWith("hyprstack-custom-")))
                root.reload();
            if (root.operation === "apply" || (root.operation === "refresh" && root.result.updated))
                Colours.reload();
            if (root.operation === "import" && root.result.id) {
                const theme = root.result;
                const mode = theme.variants.find(v => v.mode === root.requestedMode)?.mode ?? theme.variants[0].mode;
                Qt.callLater(() => root.apply(theme.id, mode));
            }
        }
    }
}
