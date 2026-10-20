pragma Singleton

import QtQuick
import Quickshell
import Quickshell.Io
import Hyprstack.I18n
import qs.services
import qs.utils

Singleton {
    id: root

    readonly property string configPath: `${Paths.config}/monitors.lua`
    readonly property list<var> monitors: parseMonitors()
    readonly property list<var> arranged: monitors.map(m => stagedFor(m.name))
    readonly property bool hasStaged: Object.keys(staged).length > 0

    property var staged: ({})
    property string existingConfig: ""
    property var modesByName: ({})

    readonly property string monitorSignature: Hypr.monitors.values.map(m => m.name).join(",")

    readonly property string blockStart: "-- Hyprstack display settings: start"
    readonly property string blockEnd: "-- Hyprstack display settings: end"

    Component.onCompleted: {
        configFile.reload();
        refreshModes();
    }

    onMonitorSignatureChanged: refreshModes()

    Connections {
        function onConfigReloaded(): void {
            refreshModes();
        }

        target: Hypr
    }

    function parseMonitors(): list<var> {
        const list = [];
        for (const mon of Hypr.monitors.values) {
            const ipc = mon.lastIpcObject;
            if (!ipc || ipc.disabled === true)
                continue;
            list.push(parseMonitor(ipc));
        }
        return list;
    }

    function parseMonitor(ipc: var): var {
        const scale = ipc.scale || 1;
        const transform = ipc.transform ?? 0;
        const rotated = [1, 3, 5, 7].includes(transform);
        const width = ipc.width ?? 0;
        const height = ipc.height ?? 0;
        const modes = parseModes(ipc);
        const resolution = `${width}x${height}`;
        const group = modes.find(g => g.res === resolution) ?? null;
        const rate = group ? nearestRate(group, ipc.refreshRate ?? 60) : (ipc.refreshRate ?? 60);
        return {
            name: ipc.name ?? "",
            description: ipc.description || `${ipc.make ?? ""} ${ipc.model ?? ""}`.trim() || ipc.name || "",
            x: ipc.x ?? 0,
            y: ipc.y ?? 0,
            scale: scale,
            transform: transform,
            rawWidth: width,
            rawHeight: height,
            vrr: (ipc.vrr === undefined || ipc.vrr === null) ? null : vrrToInt(ipc.vrr),
            focused: ipc.focused === true,
            dpms: ipc.dpmsStatus !== false,
            logicalWidth: (rotated ? height : width) / scale,
            logicalHeight: (rotated ? width : height) / scale,
            resolution: resolution,
            rate: rate,
            mode: group ? modeForRate(group, rate) : `${resolution}@${formatRate(rate)}`,
            modes: modes
        };
    }

    function parseModes(ipc: var): list<var> {
        // Quickshell's typed monitor object does not expose availableModes,
        // so the full mode list is fetched separately via hyprctl.
        const raw = modesByName[ipc.name] ?? ipc.availableModes;
        const groups = new Map();
        if (Array.isArray(raw)) {
            for (const entry of raw) {
                const str = String(entry);
                const at = str.lastIndexOf("@");
                if (at <= 0)
                    continue;
                const res = str.slice(0, at);
                const rate = Number(str.slice(at + 1).replace("Hz", ""));
                if (!res || !isFinite(rate))
                    continue;
                if (!groups.has(res))
                    groups.set(res, {
                        res: res,
                        rates: [],
                        modes: ({})
                    });
                const group = groups.get(res);
                if (!group.modes.hasOwnProperty(rate)) {
                    group.rates.push(rate);
                    group.modes[rate] = str.endsWith("Hz") ? str.slice(0, -2) : str;
                }
            }
        }
        if (groups.size === 0 && ipc.width > 0 && ipc.height > 0) {
            const res = `${ipc.width}x${ipc.height}`;
            const rate = Number(formatRate(ipc.refreshRate ?? 60));
            const group = {
                res: res,
                rates: [rate],
                modes: ({})
            };
            group.modes[rate] = `${res}@${formatRate(rate)}`;
            groups.set(res, group);
        }
        const list = [...groups.values()];
        for (const group of list)
            group.rates.sort((a, b) => b - a);
        return list;
    }

    function vrrToInt(vrr: var): int {
        if (vrr === true)
            return 1;
        if (vrr === false)
            return 0;
        const n = Number(vrr);
        return isFinite(n) ? n : 0;
    }

    function formatRate(rate: real): string {
        return String(Math.round(rate * 100) / 100);
    }

    function nearestRate(group: var, rate: real): real {
        let best = group.rates[0] ?? rate;
        let bestDiff = Math.abs(best - rate);
        for (const r of group.rates) {
            const diff = Math.abs(r - rate);
            if (diff < bestDiff) {
                best = r;
                bestDiff = diff;
            }
        }
        return best;
    }

    function modeForRate(group: var, rate: real): string {
        return group.modes[nearestRate(group, rate)] ?? "";
    }

    function copyFields(from: var, to: var): var {
        for (const key of Object.keys(from ?? {}))
            to[key] = from[key];
        return to;
    }

    // Live view of one monitor merged with its staged patch, if any
    function stagedFor(name: string): var {
        const live = monitors.find(m => m.name === name);
        const patch = staged[name];
        if (!live) {
            if (!patch)
                return null;
            const orphan = {
                name: name
            };
            return copyFields(patch, orphan);
        }
        const merged = copyFields(live, {});
        copyFields(patch, merged);
        if (patch?.mode) {
            const at = patch.mode.lastIndexOf("@");
            if (at > 0) {
                merged.resolution = patch.mode.slice(0, at);
                merged.rate = Number(patch.mode.slice(at + 1)) || merged.rate;
                const x = merged.resolution.indexOf("x");
                if (x > 0) {
                    merged.rawWidth = Number(merged.resolution.slice(0, x)) || merged.rawWidth;
                    merged.rawHeight = Number(merged.resolution.slice(x + 1)) || merged.rawHeight;
                }
            }
        }
        if (patch && (patch.mode !== undefined || patch.scale !== undefined || patch.transform !== undefined)) {
            const rotated = [1, 3, 5, 7].includes(merged.transform ?? 0);
            const w = merged.rawWidth ?? 0;
            const h = merged.rawHeight ?? 0;
            merged.logicalWidth = (rotated ? h : w) / (merged.scale || 1);
            merged.logicalHeight = (rotated ? w : h) / (merged.scale || 1);
        }
        return merged;
    }

    function stage(name: string, patch: var): void {
        const next = copyFields(staged, {});
        next[name] = copyFields(patch, copyFields(staged[name] ?? {}, {}));
        staged = next;
    }

    function stageResolution(name: string, res: string): void {
        const view = stagedFor(name);
        const group = view?.modes?.find(g => g.res === res);
        if (!view || !group)
            return;
        const rate = group.rates.includes(view.rate) ? view.rate : nearestRate(group, view.rate);
        stageMode(name, group.modes[rate]);
    }

    function stageMode(name: string, mode: string): void {
        stage(name, {
            mode: mode
        });
    }

    function stageRate(name: string, rate: real): void {
        const view = stagedFor(name);
        if (!view)
            return;
        let res = view.resolution;
        if (view.mode) {
            const at = view.mode.lastIndexOf("@");
            if (at > 0)
                res = view.mode.slice(0, at);
        }
        const group = view.modes.find(g => g.res === res);
        if (group)
            stageMode(name, modeForRate(group, rate));
    }

    function stagePosition(name: string, x: real, y: real): void {
        stage(name, {
            x: Math.round(x),
            y: Math.round(y)
        });
    }

    function stageScale(name: string, scale: real): void {
        stage(name, {
            scale: scale
        });
    }

    function stageVrr(name: string, vrr: int): void {
        stage(name, {
            vrr: vrr
        });
    }

    function stageTransform(name: string, transform: int): void {
        stage(name, {
            transform: transform
        });
    }

    function revert(): void {
        staged = ({});
    }

    function refreshModes(): void {
        if (!modesProc.running)
            modesProc.running = true;
    }

    function apply(): void {
        const views = [];
        for (const name of Object.keys(staged)) {
            if (monitors.find(m => m.name === name))
                views.push(stagedFor(name));
        }
        if (!views.length) {
            staged = ({});
            return;
        }

        if (Hypr.usingLua) {
            for (const view of views)
                Hypr.extras.message(`eval hl.monitor(${luaTable(view)})`);
        } else {
            const batch = views.map(v => {
                let rule = `${v.name}, ${currentMode(v)}, ${Math.round(v.x)}x${Math.round(v.y)}, ${formatScale(v.scale)}, ${v.transform ?? 0}`;
                if (v.vrr != null)
                    rule += `, vrr, ${v.vrr}`;
                return `keyword monitor '${rule}'`;
            }).join("; ");
            hyprctlProc.command = ["hyprctl", "--batch", batch];
            hyprctlProc.running = true;
        }

        writeConfig();
        staged = ({});
    }

    function currentMode(view: var): string {
        if (view.mode)
            return view.mode;
        if (view.resolution)
            return `${view.resolution}@${formatRate(view.rate ?? 60)}`;
        return "preferred";
    }

    function luaTable(view: var): string {
        const parts = [`output = ${luaString(view.name)}`, `mode = ${luaString(currentMode(view))}`, `position = ${luaString(`${Math.round(view.x ?? 0)}x${Math.round(view.y ?? 0)}`)}`, `scale = ${formatScale(view.scale ?? 1)}`, `transform = ${view.transform ?? 0}`];
        if (view.vrr != null)
            parts.push(`vrr = ${view.vrr}`);
        return `{ ${parts.join(", ")} }`;
    }

    function luaString(value: string): string {
        return `"${String(value).replace(/\\/g, "\\\\").replace(/"/g, '\\"')}"`;
    }

    function formatScale(scale: real): string {
        return String(Math.round(scale * 100) / 100);
    }

    // monitors.lua writer: replace (or append) the marked managed block and
    // keep everything outside the markers verbatim
    function writeConfig(): void {
        if (writer.running)
            return;
        writer.payload = buildConfig(existingConfig);
        writer.command = ["sh", "-c", `cat > ${shellQuote(configPath)}`];
        writer.running = true;
    }

    function buildConfig(existing: string): string {
        const header = `-- ${Tr.tr("Generated by Hyprstack Display settings; content outside the markers is preserved.")}`;
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
                if (prevLine.startsWith("-- Generated by Hyprstack Display settings") || prevLine.startsWith("-- Сгенерировано настройками экрана Hyprstack"))
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
        const lines = [];
        for (const view of arranged) {
            if (view)
                lines.push(`hl.monitor(${luaTable(view)})`);
        }
        return lines.join("\n");
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
    }

    Process {
        id: modesProc

        command: ["hyprctl", "monitors", "all", "-j"]
        stdout: StdioCollector {
            onStreamFinished: {
                try {
                    const all = JSON.parse(text);
                    const map = ({});
                    for (const mon of all) {
                        if (Array.isArray(mon.availableModes) && mon.availableModes.length > 0 && mon.name)
                            map[mon.name] = mon.availableModes;
                    }
                    root.modesByName = map;
                } catch (err) {
                    console.warn("Monitors: unable to parse available modes");
                }
            }
        }
    }
}
