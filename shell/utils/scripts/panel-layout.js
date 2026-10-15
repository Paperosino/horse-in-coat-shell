.pragma library

function centeredWidth(width, left, right, gap) {
    return Math.max(0, width - 2 * (Math.max(left, right) + gap));
}

function workspaceIds(offset, count, activeId, occupiedIds, showUnoccupied) {
    let last = showUnoccupied ? count : Math.max(1, activeId - offset);
    if (!showUnoccupied) {
        for (const id of occupiedIds) {
            if (id > offset && id <= offset + count)
                last = Math.max(last, id - offset);
        }
    }
    last = Math.max(1, Math.min(count, last));
    return Array.from({length: last}, (_, i) => offset + i + 1);
}
