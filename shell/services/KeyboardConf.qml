pragma Singleton

import QtQuick
import Quickshell
import Quickshell.Io
import Hyprstack.I18n
import qs.services
import qs.utils

Singleton {
    id: root

    readonly property string configPath: `${Paths.config}/keyboard.lua`

    readonly property string blockStart: "-- Hyprstack keyboard settings: start"
    readonly property string blockEnd: "-- Hyprstack keyboard settings: end"

    // xkb rules data, parsed from base.lst
    property list<var> layouts: []
    property var variantsByLayout: ({})

    // Editable state
    property list<string> layoutCodes: ["us"]
    property var variantByLayout: ({})
    property string switchOption: ""
    property string capsOption: ""
    property string composeOption: ""
    property bool numlock: false
    property int repeatDelay: 600
    property int repeatRate: 25

    // Live results, also shown on the Configuration section of the page
    readonly property string layoutCsv: layoutCodes.join(",")
    readonly property string variantCsv: buildVariantCsv()
    readonly property string optionsCsv: buildOptionsCsv()

    readonly property var mainKeyboard: Hypr.keyboard

    property var existingConfig: ""
    property bool layoutsLoaded: false
    property bool typingLoaded: false
    property bool applyQueued: false

    Component.onCompleted: {
        rulesFile.reload();
        configFile.reload();
        if (!typingProc.running)
            typingProc.running = true;
    }

    onMainKeyboardChanged: {
        if (layoutsLoaded || !mainKeyboard)
            return;
        adoptLayouts();
        layoutsLoaded = true;
    }

    function nameForLayout(code: string): string {
        const layout = layouts.find(l => l.code === code);
        return layout ? layout.name : code;
    }

    function variantsFor(code: string): list<var> {
        return variantsByLayout[code] ?? [];
    }

    // Adopt the running compositor state once, on startup. The compositor
    // state reflects keyboard.lua (loaded by hypr-user.lua) plus any manual
    // runtime changes, so it is the best initial view of the configuration.
    function adoptLayouts(): void {
        const codes = String(mainKeyboard.layout ?? "").split(",").map(code => code.trim()).filter(code => code.length > 0);
        layoutCodes = codes.length ? [...new Set(codes)] : ["us"];
        const variantMap = ({});
        const variants = String(mainKeyboard.lastIpcObject?.variant ?? "").split(",");
        for (let i = 0; i < layoutCodes.length; i++) {
            const variant = (variants[i] ?? "").trim();
            if (variant)
                variantMap[layoutCodes[i]] = variant;
        }
        variantByLayout = variantMap;
        const options = String(mainKeyboard.lastIpcObject?.options ?? "").split(",").map(option => option.trim()).filter(option => option.length > 0);
        switchOption = options.find(option => option.startsWith("grp:")) ?? "";
        capsOption = options.find(option => option.startsWith("caps:")) ?? "";
        composeOption = options.find(option => option.startsWith("compose:")) ?? "";
    }

    // xkb rules parsing (base.lst): layout lines are "code<TAB>Description",
    // variant lines are "variant<TAB>layout_code: Description".
    function parseRules(text: string): void {
        const layoutMap = new Map();
        const variantMap = new Map();
        let section = "";
        for (const line of text.split(/\r?\n/)) {
            const header = line.match(/^!\s+(\w+)/);
            if (header) {
                section = header[1];
                continue;
            }
            if (section === "layout") {
                const match = line.match(/^\s*(\S+)\s+(.+?)\s*$/);
                if (match && !layoutMap.has(match[1]))
                    layoutMap.set(match[1], match[2]);
            } else if (section === "variant") {
                const match = line.match(/^\s*(\S+)\s+(\S+):\s*(.+?)\s*$/);
                if (match) {
                    if (!variantMap.has(match[2]))
                        variantMap.set(match[2], []);
                    variantMap.get(match[2]).push({
                        code: match[1],
                        name: match[3]
                    });
                }
            }
        }
        const defaultEntry = {
            code: "",
            // TRANSLATORS: the default variant of a keyboard layout (no variant selected)
            name: Tr.tr("Default")
        };
        const variants = ({});
        for (const [code, list] of variantMap) {
            list.sort((a, b) => a.name.localeCompare(b.name));
            variants[code] = [defaultEntry, ...list];
        }
        const sorted = [];
        for (const [code, name] of layoutMap)
            sorted.push({
                code: code,
                name: name
            });
        sorted.sort((a, b) => a.name.localeCompare(b.name));
        variantsByLayout = variants;
        layouts = sorted;
    }

    function addLayout(code: string): void {
        if (!code || layoutCodes.includes(code))
            return;
        layoutCodes = [...layoutCodes, code];
        changed();
    }

    function removeLayout(index: int): void {
        if (index < 0 || index >= layoutCodes.length)
            return;
        const next = [...layoutCodes];
        next.splice(index, 1);
        // Hyprland requires at least one layout
        layoutCodes = next.length ? next : ["us"];
        changed();
    }

    function moveLayout(from: int, to: int): void {
        if (from === to || from < 0 || to < 0 || from >= layoutCodes.length || to >= layoutCodes.length)
            return;
        const next = [...layoutCodes];
        next.splice(to, 0, ...next.splice(from, 1));
        layoutCodes = next;
        changed();
    }

    function setVariant(layout: string, variant: string): void {
        const next = Object.assign({}, variantByLayout);
        next[layout] = variant ?? "";
        variantByLayout = next;
        changed();
    }

    function setSwitchOption(option: string): void {
        switchOption = option ?? "";
        changed();
    }

    function setCapsOption(option: string): void {
        capsOption = option ?? "";
        changed();
    }

    function setComposeOption(option: string): void {
        composeOption = option ?? "";
        changed();
    }

    function setNumlock(value: bool): void {
        numlock = value;
        changed();
    }

    function setRepeatDelay(value: int): void {
        repeatDelay = Math.max(0, Math.round(value));
        changed();
    }

    function setRepeatRate(value: int): void {
        repeatRate = Math.max(0, Math.round(value));
        changed();
    }

    function changed(): void {
        applyLive();
        writeTimer.restart();
    }

    function buildVariantCsv(): string {
        const parts = [];
        for (const code of layoutCodes)
            parts.push(variantByLayout[code] ?? "");
        return parts.join(",");
    }

    function buildOptionsCsv(): string {
        return [switchOption, capsOption, composeOption].filter(option => option.length > 0).join(",");
    }

    function applyLive(): void {
        if (hyprctlProc.running) {
            applyQueued = true;
            return;
        }
        startApply();
    }

    function startApply(): void {
        if (Hypr.usingLua) {
            // This compositor uses the Lua config engine, where the legacy
            // "keyword" command is unavailable; hl.config is the runtime API.
            const parts = [`kb_layout = ${luaString(layoutCsv)}`, `kb_variant = ${luaString(variantCsv)}`, `kb_options = ${luaString(optionsCsv)}`, `numlock_by_default = ${numlock}`, `repeat_delay = ${repeatDelay}`, `repeat_rate = ${repeatRate}`];
            hyprctlProc.command = ["hyprctl", "--batch", `eval hl.config({ input = { ${parts.join(", ")} } })`];
        } else {
            const parts = [`keyword input:kb_layout '${layoutCsv}'`, `keyword input:kb_variant '${variantCsv}'`, `keyword input:kb_options '${optionsCsv}'`, `keyword input:numlock_by_default '${numlock}'`, `keyword input:repeat_delay '${repeatDelay}'`, `keyword input:repeat_rate '${repeatRate}'`];
            hyprctlProc.command = ["hyprctl", "--batch", parts.join("; ")];
        }
        hyprctlProc.running = true;
    }

    function luaString(value: string): string {
        return `"${String(value).replace(/\\/g, "\\\\").replace(/"/g, '\\"')}"`;
    }

    // keyboard.lua writer: replace (or append) the marked managed block and
    // keep everything outside the markers verbatim
    function writeConfig(): void {
        if (writer.running) {
            writeTimer.restart();
            return;
        }
        writer.payload = buildConfig(existingConfig);
        writer.command = ["sh", "-c", `cat > ${shellQuote(configPath)}`];
        writer.running = true;
    }

    function buildConfig(existing: string): string {
        const header = `-- ${Tr.tr("Generated by Hyprstack Keyboard settings; content outside the markers is preserved.")}`;
        const managed = `${blockStart}\n${header}\n${managedBlock()}\n${blockEnd}\n`;
        const sIdx = existing.indexOf(blockStart);
        const eIdx = existing.indexOf(blockEnd);
        if (sIdx >= 0 && eIdx > sIdx) {
            // Consume header comments older writer versions left above the
            // start marker (English or translated).
            let begin = lineStart(existing, sIdx);
            while (begin > 0) {
                const prevBegin = lineStart(existing, begin - 1);
                const prevLine = existing.slice(prevBegin, begin).trimEnd();
                if (prevLine.startsWith("-- Generated by Hyprstack Keyboard settings") || prevLine.startsWith("-- Сгенерировано настройками клавиатуры Hyprstack"))
                    begin = prevBegin;
                else
                    break;
            }
            const finish = lineEnd(existing, eIdx);
            return existing.slice(0, begin) + managed + existing.slice(finish);
        }
        if (!existing.trim())
            return managed;
        return existing + (existing.endsWith("\n") ? "" : "\n") + `\n${managed}`;
    }

    function managedBlock(): string {
        const parts = [`kb_layout = ${luaString(layoutCsv)}`];
        if (variantCsv)
            parts.push(`kb_variant = ${luaString(variantCsv)}`);
        if (optionsCsv)
            parts.push(`kb_options = ${luaString(optionsCsv)}`);
        if (numlock)
            parts.push("numlock_by_default = true");
        if (repeatDelay !== 600)
            parts.push(`repeat_delay = ${repeatDelay}`);
        if (repeatRate !== 25)
            parts.push(`repeat_rate = ${repeatRate}`);
        return `hl.config({ input = { ${parts.join(", ")} } })`;
    }

    function lineStart(text: string, idx: int): int {
        const nl = text.lastIndexOf("\n", idx - 1);
        return nl < 0 ? 0 : nl + 1;
    }

    function lineEnd(text: string, idx: int): int {
        const nl = text.indexOf("\n", idx);
        return nl < 0 ? text.length : nl + 1;
    }

    function shellQuote(path: string): string {
        return `'${path.replace(/'/g, "'\"'\"'")}'`;
    }

    Timer {
        id: writeTimer

        interval: 300
        onTriggered: root.writeConfig()
    }

    FileView {
        id: rulesFile

        path: Hypr.xkbRulesPath
        onLoaded: root.parseRules(text())
    }

    FileView {
        id: configFile

        path: root.configPath
        watchChanges: true
        printErrors: false
        onFileChanged: reload()
        onLoaded: root.existingConfig = text()
    }

    Process {
        id: writer

        property string payload: ""

        stdinEnabled: true
        onStarted: {
            writer.write(payload);
            writer.stdinEnabled = false;
        }
    }

    Process {
        id: hyprctlProc

        onExited: {
            if (root.applyQueued) {
                root.applyQueued = false;
                root.startApply();
            }
        }
    }

    // Seed numlock/repeat from the compositor once. Hypr.options is fed by
    // "descriptions" which does not reflect live values on the Lua engine,
    // so getoption is used instead. Failures leave the Hyprland defaults.
    Process {
        id: typingProc

        command: ["sh", "-c", "hyprctl getoption input:repeat_delay -j; hyprctl getoption input:repeat_rate -j; hyprctl getoption input:numlock_by_default -j"]
        stdout: StdioCollector {
            onStreamFinished: {
                if (root.typingLoaded)
                    return;
                try {
                    for (const line of text.split("\n")) {
                        if (!line.trim())
                            continue;
                        const entry = JSON.parse(line);
                        if (entry.option === "input:repeat_delay" && typeof entry.int === "number")
                            root.repeatDelay = entry.int;
                        else if (entry.option === "input:repeat_rate" && typeof entry.int === "number")
                            root.repeatRate = entry.int;
                        else if (entry.option === "input:numlock_by_default")
                            root.numlock = entry.bool === true;
                    }
                } catch (err) {
                    console.warn("KeyboardConf: unable to read input options");
                }
                root.typingLoaded = true;
            }
        }
    }
}
