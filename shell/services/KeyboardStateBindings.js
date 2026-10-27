.pragma library

// The flag lives in Hyprland's Lua state, not the shell process. A config reload
// replaces that state and clears its dynamic bindings, so installation runs again.
var luaCommand = 'eval if not rawget(_G,"hics_keyboard_state_bindings") then hl.bind("Caps_Lock",hl.dsp.global("hyprstack:refreshDevices"),{locked=true,non_consuming=true,ignore_mods=true,release=true});hl.bind("Num_Lock",hl.dsp.global("hyprstack:refreshDevices"),{locked=true,non_consuming=true,ignore_mods=true,release=true});_G.hics_keyboard_state_bindings=true end';

function create() {
    let pending = false, rerun = false, generation = 0;
    let latestTransport, latestLua;
    function send() {
        pending = true;
        const transport = latestTransport, lua = latestLua, current = generation;
        let finished = false;
        function done(ok, response) {
            if (finished) return;
            finished = true;
            if (!ok) console.warn("Unable to install keyboard-state shortcuts");
            pending = false;
            if (rerun) { rerun = false; send(); }
        }
        if (lua) {
            transport.request(luaCommand, (ok, response) => done(ok && response.trim() === "ok", response));
            return;
        }
        transport.request("j/binds", (ok, response) => {
            // A snapshot from before a reload/parser change cannot authorize a write.
            if (current !== generation || lua !== latestLua) { done(true, ""); return; }
            if (!ok) { done(false, ""); return; }
            let binds;
            try { binds = JSON.parse(response); } catch (_) { done(false, ""); return; }
            if (!Array.isArray(binds)) { done(false, ""); return; }
            const commands = [];
            for (const key of ["Caps_Lock", "Num_Lock"]) {
                const exists = binds.some(b => b && typeof b === "object" && b.key === key && b.modmask === 0 && b.submap === ""
                    && b.dispatcher === "global" && b.arg === "hyprstack:refreshDevices"
                    && b.locked === true && b.non_consuming === true && b.release === false);
                if (!exists) commands.push("keyword bindlni ," + key + ",global,hyprstack:refreshDevices");
            }
            if (!commands.length) { done(true, ""); return; }
            // Keep the queue busy through the commit response, not just the query.
            transport.request("[[BATCH]]" + commands.join(";"), (success, reply) => {
                const valid = reply.trim().split(/\n+/).every(line => line.trim() === "ok");
                done(success && valid, reply);
            });
        });
    }
    return {
        busy: function() { return pending; },
        update: function(transport, lua) {
            ++generation;
            latestTransport = transport; latestLua = lua;
            if (pending) { rerun = true; return; }
            send();
        }
    };
}
