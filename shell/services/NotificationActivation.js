// Match application identities, never notification text or a partial title.
function normalise(value) {
    return String(value || "").toLowerCase().replace(/\.desktop$/, "").replace(/[^a-z0-9а-яё]/g, "");
}

function identities(value) {
    var groups = [
        ["org.telegram.desktop", "telegram-desktop", "TelegramDesktop", "Telegram"],
        ["com.ayugram.desktop", "AyugramDesktop", "AyuGram"],
        ["com.discordapp.Discord", "discord"],
        ["org.mozilla.firefox", "firefox"]
    ];
    var key = normalise(value);
    if (!key) return [];
    var group = groups.find(g => g.some(id => normalise(id) === key));
    return group ? group.map(normalise) : [key];
}

function overlaps(left, right) {
    return left.some(id => right.includes(id));
}

function desktopEntry(notification, entries) {
    var ids = identities(notification.desktopEntry);
    var exact = entries.find(entry => overlaps(ids, identities(entry.id)));
    if (exact) return exact;
    // A supplied desktop ID is authoritative: do not launch a different app
    // just because it has the same display name.
    if (ids.length) return null;
    var names = identities(notification.appName);
    var matches = entries.filter(entry => overlaps(names, identities(entry.name))
        || overlaps(names, identities(entry.id)) || overlaps(names, identities(entry.startupClass)));
    return matches.length === 1 ? matches[0] : null;
}

function windowScore(notification, entry, window) {
    var ipc = window.lastIpcObject || {};
    if (!ipc.mapped) return 0;
    var classes = identities(ipc.class).concat(identities(ipc.initialClass));
    var strong = identities(notification.desktopEntry);
    if (entry) strong = strong.concat(identities(entry.id), identities(entry.startupClass));
    if (overlaps(strong, classes)) return 100;
    // When a desktop ID is present, names alone cannot override it.
    if (!strong.length && overlaps(identities(notification.appName), classes)) return 80;
    return 0;
}

function bestWindow(notification, entry, windows) {
    return windows.filter(window => windowScore(notification, entry, window) > 0).sort((a, b) => {
        var score = windowScore(notification, entry, b) - windowScore(notification, entry, a);
        if (score) return score;
        var recent = window => {
            var value = window.lastIpcObject.focusHistoryID;
            return value >= 0 ? value : Number.MAX_SAFE_INTEGER;
        };
        return recent(a) - recent(b);
    })[0] || null;
}

function followWindow(notification, entry, windows, active) {
    // Keep the exact window selected by the application when it is known.
    if (active && windowScore(notification, entry, active) > 0) return active;
    return bestWindow(notification, entry, windows);
}
