// Pure data conversion. Functions/actions and transient popups never reach disk.
function localPath(value) {
    if (typeof value !== "string") return "";
    if (value.startsWith("/")) return value;
    if (/^file:\/\/(localhost)?\//.test(value)) {
        try { return decodeURIComponent(value.replace(/^file:\/\/(localhost)?/, "")); }
        catch (_) { return ""; }
    }
    return "";
}

function imagePath(notification) {
    const hints = notification.hints || {};
    return localPath(hints["image-path"] || hints.image_path || "")
        || localPath(notification.image || "") || localPath(notification.appIcon || "");
}

function isScreenshot(notification, path) {
    const hints = notification.hints || {};
    return hints.category === "screenshot" || !!hints["x-hyprstack-screenshot"]
        || /spectacle|flameshot|screenshot|grim|swappy/i.test(notification.appName || "")
        || (!!path && (/screenshot|скриншот|снимок экрана/i.test(notification.summary || "")
            || /(?:screenshots|hyprstack-picker)[/-]/i.test(path)));
}

function serialize(notification) {
    return {
        historyId: notification.historyId, notificationId: notification.notificationId,
        time: notification.time, read: notification.read, summary: notification.summary,
        body: notification.body, appIcon: notification.appIcon, appName: notification.appName,
        image: notification.image.startsWith("image://") ? "" : notification.image,
        screenshot: notification.screenshot, screenshotPath: notification.screenshotPath,
        desktopEntry: notification.desktopEntry, urgency: notification.urgency,
        expireTimeout: notification.expireTimeout, resident: notification.resident
    };
}

function restore(data) {
    const records = Array.isArray(data) ? data : data.notifications;
    if (!Array.isArray(records)) throw new Error("Invalid notification history");
    const seen = new Set();
    const notifications = [];
    for (const record of records.slice(0, 500)) {
        if (!record || typeof record !== "object" || typeof record.summary !== "string") continue;
        const time = new Date(record.time);
        if (!Number.isFinite(time.getTime())) continue;
        const historyId = String(record.historyId || "saved-" + time.getTime() + "-" + notifications.length);
        if (seen.has(historyId)) continue;
        seen.add(historyId);
        const result = {historyId, time, read: record.read === true, popup: false,
            notificationId: String(record.notificationId ?? record.id ?? ""),
            summary: record.summary, urgency: [0, 1, 2].includes(record.urgency) ? record.urgency : 1};
        for (const key of ["body", "appName", "appIcon", "image", "desktopEntry", "screenshotPath"])
            result[key] = typeof record[key] === "string" ? record[key] : "";
        if (result.image.startsWith("image://")) result.image = "";
        result.screenshotPath = localPath(result.screenshotPath);
        result.screenshot = record.screenshot === true || isScreenshot(result, imagePath(result));
        if (result.screenshot && !result.screenshotPath) result.screenshotPath = imagePath(result);
        result.resident = record.resident === true;
        notifications.push(result);
    }
    notifications.sort((a, b) => b.time - a.time);
    return {notifications, dnd: !Array.isArray(data) && data.dnd === true};
}
