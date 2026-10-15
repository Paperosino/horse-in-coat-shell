.pragma library

// Logical monitor coordinates. Hyprland renders these transforms directly;
// clients keep their real size, workspace and layout throughout the overview.
function grid(windows, width, height) {
    if (!windows.length) return [];
    var margin = Math.min(48, width * 0.045);
    var top = Math.min(48, height * 0.06), bottom = top;
    var areaW = Math.max(1, width - margin * 2), areaH = Math.max(1, height - top - bottom);
    var density = Math.max(1, Math.ceil(Math.sqrt(windows.length * areaH / areaW)));
    var gap = Math.min(28, areaW * 0.025, areaH / (density * 3));
    var best = {score: -1};
    for (var columns = 1; columns <= windows.length; columns++) {
        var rows = Math.ceil(windows.length / columns);
        var cellW = (areaW - gap * (columns - 1)) / columns;
        var cellH = (areaH - gap * (rows - 1)) / rows;
        if (cellW <= 0 || cellH <= 0) continue;
        var score = 0;
        windows.forEach(function(win) {
            var ext = win.extents || {};
            var scale = Math.min(cellW / (win.width + (ext.left || 0) + (ext.right || 0)),
                cellH / (win.height + (ext.top || 0) + (ext.bottom || 0)), 0.82);
            score += win.width * win.height * scale * scale;
        });
        if (score > best.score) best = {score: score, columns: columns, cellW: cellW, cellH: cellH, rows: rows};
    }
    return windows.map(function(win, index) {
        var ext = win.extents || {};
        var outerW = win.width + (ext.left || 0) + (ext.right || 0);
        var outerH = win.height + (ext.top || 0) + (ext.bottom || 0);
        var scale = Math.min(best.cellW / outerW, best.cellH / outerH, 0.82);
        var w = win.width * scale, h = win.height * scale;
        var row = Math.floor(index / best.columns), col = index % best.columns;
        var rowCount = Math.min(best.columns, windows.length - row * best.columns);
        var rowWidth = rowCount * best.cellW + (rowCount - 1) * gap;
        return {address: win.address,
            x: (width - rowWidth) / 2 + col * (best.cellW + gap) + (best.cellW - outerW * scale) / 2 + (ext.left || 0) * scale,
            y: top + row * (best.cellH + gap) + (best.cellH - outerH * scale) / 2 + (ext.top || 0) * scale,
            width: w, height: h};
    });
}

// Trim only the empty ends. Empty workspaces inside the occupied range remain
// part of the ribbon, including when more than one separates two occupied ones.
function workspaceIds(snapshot) {
    var ids = snapshot.workspaces || [], windows = snapshot.windows || [];
    var occupied = ids.filter(function(id) { return windows.some(function(w) { return w.workspace === id; }); });
    return occupied.length ? ids.slice(ids.indexOf(occupied[0]), ids.indexOf(occupied[occupied.length - 1]) + 1) : [];
}

function scrolling(snapshot, width, height, selected, workspace) {
    var zoom = 0.4;
    // Keep the workspace ribbon perpendicular to the application's tape.
    // Portrait applications can extend vertically beyond the viewport without
    // overlapping the next workspace's windows in overview.
    var portrait = snapshot.height > snapshot.width;
    var stride = portrait ? snapshot.width : snapshot.height;
    var ids = workspaceIds(snapshot);
    var current = Math.max(0, ids.indexOf(workspace));
    var focus = (snapshot.windows || []).find(function(w) { return w.address === selected && w.workspace === workspace; });
    var centerX = focus ? focus.x + focus.width / 2 : snapshot.width / 2;
    var centerY = focus ? focus.y + focus.height / 2 : snapshot.height / 2;
    var camera = {zoom: zoom,
        x: width / 2 - (portrait ? current * stride + snapshot.width / 2 : centerX) * zoom,
        y: height / 2 - (portrait ? centerY : current * stride + snapshot.height / 2) * zoom};
    var worldFrames = [], worldRows = [];
    ids.forEach(function(id, index) {
        var windows = (snapshot.windows || []).filter(function(w) { return w.workspace === id; });
        // Preserve the native positions of offscreen columns, shared rows and
        // floats. Every workspace belongs to the same continuous camera space.
        var left = 0, right = snapshot.width, top = 0, bottom = snapshot.height;
        windows.forEach(function(win) {
            left = Math.min(left, win.x - 12); right = Math.max(right, win.x + win.width + 12);
            top = Math.min(top, win.y - 12); bottom = Math.max(bottom, win.y + win.height + 12);
        });
        var originX = portrait ? index * stride : 0, originY = portrait ? 0 : index * stride;
        worldRows.push({workspace: id, x: portrait ? originX : left, y: portrait ? top : originY,
            width: portrait ? snapshot.width : right - left, height: portrait ? bottom - top : snapshot.height,
            originX: originX, originY: originY});
        windows.forEach(function(win) {
            worldFrames.push({address: win.address, x: originX + win.x, y: originY + win.y, width: win.width, height: win.height});
        });
    });
    function project(rect) {
        return Object.assign({}, rect, {x: camera.x + rect.x * zoom, y: camera.y + rect.y * zoom,
            width: rect.width * zoom, height: rect.height * zoom});
    }
    // An opening empty workspace outside the ribbon still has its own origin;
    // cancelling returns there without adding a visible empty row at either end.
    var bank = snapshot.workspaces || [];
    var origin = Math.max(0, bank.indexOf(snapshot.workspace)) - Math.max(0, bank.indexOf(ids[0]));
    return {frames: worldFrames.map(project), rows: worldRows.map(project), worldFrames: worldFrames,
        worldRows: worldRows, camera: camera,
        originCamera: {zoom: 1, x: portrait ? -origin * stride : 0, y: portrait ? 0 : -origin * stride}};
}

function neighbor(frames, index, dx, dy) {
    if (!frames.length) return -1;
    if (index < 0 || index >= frames.length) return 0;
    var from = frames[index], fx = from.x + from.width / 2, fy = from.y + from.height / 2;
    var best = index, score = Infinity;
    frames.forEach(function(frame, i) {
        if (i === index) return;
        var x = frame.x + frame.width / 2 - fx, y = frame.y + frame.height / 2 - fy;
        var forward = x * dx + y * dy, sideways = Math.abs(x * dy - y * dx);
        if (forward <= 1) return;
        var candidate = forward + sideways * 2.5;
        if (candidate < score) {score = candidate; best = i;}
    });
    return best;
}

function navigate(snapshot, selected, workspace, direction, frames) {
    var windows = snapshot.windows || [];
    if (snapshot.mode === "stacking") {
        var vectors = {H: [-1, 0], L: [1, 0], K: [0, -1], J: [0, 1]};
        var vector = vectors[direction];
        if (!vector) return {address: selected, workspace: workspace};
        var index = neighbor(frames, frames.findIndex(function(f) { return f.address === selected; }), vector[0], vector[1]);
        return {address: index < 0 ? "" : frames[index].address, workspace: workspace};
    }
    var local = windows.filter(function(w) { return w.workspace === workspace; });
    var chosen = windows.find(function(w) { return w.address === selected; });
    if (direction === "J" || direction === "K") {
        var ids = workspaceIds(snapshot);
        var at = ids.indexOf(workspace);
        var next = at + (direction === "J" ? 1 : -1);
        if (next < 0 || next >= ids.length) return {address: selected, workspace: workspace};
        var target = ids[next];
        var candidates = windows.filter(function(w) { return w.workspace === target; });
        var column = chosen ? chosen.column : 0;
        candidates.sort(function(a, b) { return Math.abs((a.column || 0) - (column || 0)) - Math.abs((b.column || 0) - (column || 0)); });
        return {address: candidates.length ? candidates[0].address : "", workspace: target};
    }
    var atWindow = local.findIndex(function(w) { return w.address === selected; });
    var step = direction === "H" ? -1 : 1;
    var nextWindow = atWindow < 0 ? 0 : atWindow + step;
    // H/L navigate columns; shared-column rows do not consume horizontal steps.
    while (chosen && nextWindow >= 0 && nextWindow < local.length
            && !chosen.floating && !local[nextWindow].floating && local[nextWindow].column === chosen.column)
        nextWindow += step;
    return {address: nextWindow >= 0 && nextWindow < local.length ? local[nextWindow].address : selected, workspace: workspace};
}
