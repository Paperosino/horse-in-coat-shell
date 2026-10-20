.pragma library

function keyName(value) {
    var names = {SUPER_L: "Super", SUPER_R: "Super", Alt_L: "Alt", Alt_R: "Alt", Return: "Enter", Escape: "Esc",
        Space: "Space", space: "Space", Period: ".", Comma: ",", Minus: "−", Equal: "=",
        Backslash: "\\", Page_Up: "Page Up", Page_Down: "Page Down", mouse_down: "Wheel down",
        mouse_up: "Wheel up", "mouse:272": "Left mouse button", "mouse:273": "Right mouse button",
        "mouse:274": "Middle mouse button", XF86MonBrightnessUp: "Brightness up",
        XF86MonBrightnessDown: "Brightness down", XF86AudioRaiseVolume: "Volume up",
        XF86AudioLowerVolume: "Volume down", XF86AudioMute: "Mute audio", XF86AudioMicMute: "Mute microphone",
        XF86AudioPlay: "Play", XF86AudioPause: "Pause", XF86AudioNext: "Next track",
        XF86AudioPrev: "Previous track", XF86AudioStop: "Stop media"};
    return names[value] || value;
}

function fromHyprland(values) {
    if (!Array.isArray(values)) throw new Error("Expected a list of bindings");
    var groups = new Map();
    for (var bind of values) {
        var raw = bind.description || ((bind.dispatcher === "__lua" ? "Custom shortcut" : bind.dispatcher)
            + (bind.dispatcher === "__lua" || !bind.arg ? "" : " " + bind.arg));
        var split = raw.indexOf(": ");
        var category = split >= 0 ? raw.slice(0, split) : "Custom";
        var action = split >= 0 ? raw.slice(split + 2) : raw;
        var keys = [];
        for (var pair of [[64,"Super"],[4,"Ctrl"],[8,"Alt"],[1,"Shift"],[2,"Caps Lock"],[16,"Mod2"],[32,"Mod3"],[128,"Mod5"]])
            if (bind.modmask & pair[0]) keys.push(pair[1]);
        var key = keyName(bind.key || "code:" + bind.keycode);
        if (!keys.includes(key)) keys.push(key);
        var shortcut = keys.join(" + ");
        var identity = category + "\n" + action + "\n" + (bind.submap || "") + "\n" + !!bind.mouse;
        if (!groups.has(identity)) groups.set(identity, {category:category, action:action,
            shortcuts:[], submap:bind.submap || "", mouse:!!bind.mouse});
        var entry = groups.get(identity);
        if (!entry.shortcuts.includes(shortcut)) entry.shortcuts.push(shortcut);
    }
    var order = ["Shell","Applications","Windows","Canvas","Workspaces","Capture","Clipboard","Media","Session","Custom"];
    return Array.from(groups.values()).sort((a,b) => {
        var ai = order.indexOf(a.category), bi = order.indexOf(b.category);
        return (ai < 0 ? order.length : ai) - (bi < 0 ? order.length : bi)
            || a.category.localeCompare(b.category) || a.action.localeCompare(b.action, undefined, {numeric:true});
    });
}

function matches(entry, query, translate) {
    if (query.includes("+")) {
        var chord = query.toLowerCase().replace(/\s+/g, "");
        return [...entry.shortcuts, ...entry.shortcuts.map(value => translateShortcut(value, translate))].some(value => {
            var candidate = value.toLowerCase().replace(/\s+/g, "");
            return chord.endsWith("+") ? candidate.startsWith(chord) : candidate === chord;
        });
    }
    var text = [entry.category, entry.action, translate(entry.category), translate(entry.action),
        entry.submap, ...entry.shortcuts, ...entry.shortcuts.map(value => translateShortcut(value, translate))]
        .join(" ").toLowerCase().replace(/ё/g,"е");
    return query.trim().toLowerCase().replace(/ё/g,"е").split(/\s+/).every(token => text.includes(token));
}

// Compositor descriptions append workspace numbers and directions at runtime.
function translateDescription(text, translate) {
    var match = text.match(/^(.*) (\d+|left|right|up|down|l|r|u|d)$/);
    if (match) {
        var key = match[1] + " %1";
        var translated = translate(key);
        if (translated !== key) return translated.replace("%1", translate(match[2]));
    }
    return translate(text);
}

function translateShortcut(text, translate) {
    return text.split(" + ").map(value => translate(value)).join(" + ");
}
