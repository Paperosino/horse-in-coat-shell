#include <hyprland/src/plugins/PluginAPI.hpp>
#include <hyprland/src/desktop/state/WindowState.hpp>
#include <hyprland/src/config/ConfigManager.hpp>
#include "task-animation.hpp"
#include "focus-animation.hpp"
#include <hyprland/src/event/EventBus.hpp>
#include <hyprland/src/managers/fullscreen/FullscreenController.hpp>
extern "C" {
#include <lua.h>
#include <lauxlib.h>
}

namespace {
CHyprSignalListener fullscreenListener;
CHyprColor color(lua_State* L, int index, const char* fallback) {
    std::string value = luaL_optstring(L, index, fallback);
    if (value.starts_with('#')) value.erase(0, 1);
    if (value.size() != 6 || value.find_first_not_of("0123456789abcdefABCDEF") != std::string::npos) value = fallback;
    return CHyprColor(0xff000000ULL | std::stoul(value, nullptr, 16));
}
int animate(lua_State* L) {
    const std::string address = luaL_checkstring(L, 1), id = luaL_checkstring(L, 2), operation = luaL_checkstring(L, 3);
    PHLWINDOW window;
    for (const auto& w : Desktop::windowState()->windows()) {
        if (w->m_isMapped && std::format("0x{:x}", reinterpret_cast<uintptr_t>(w.get())) == address && std::format("{:x}", w->m_stableID) == id) { window = w; break; }
    }
    if (!window) { lua_pushboolean(L, false); return 1; }
    const auto previous = CExpressiveTaskAnimation::find(window);
    if (operation == "to" || operation == "from") CStackFocusAnimation::clear(window);
    if (operation == "busy") { lua_pushboolean(L, previous && previous->busy()); return 1; }
    if (operation == "state") {
        if (!previous) { lua_pushnil(L); return 1; }
        const auto box = previous->current();
        lua_createtable(L, 0, 5);
        for (const auto& [name, value] : std::vector<std::pair<const char*, double>>{{"x",box.x},{"y",box.y},{"width",box.w},{"height",box.h},{"progress",previous->progress()},{"renderCount",previous->renderCount()},{"paintCount",previous->paintCount()}}) {
            lua_pushnumber(L, value); lua_setfield(L, -2, name);
        }
        return 1;
    }
    if (operation == "clear") { CExpressiveTaskAnimation::clear(window); return 0; }
    const double duration = std::clamp(luaL_optnumber(L, 9, 420.0), 0.0, 700.0) / 1000.0;
    const auto current = previous ? previous->current() : window->getFullWindowBoundingBox();
    const bool reversing = previous;
    CExpressiveTaskAnimation::clear(window);
    if (duration < 0.001) return 0;
    const CBox target{{luaL_checknumber(L,4),luaL_checknumber(L,5)}, {std::max(1.0,luaL_checknumber(L,6)),std::max(1.0,luaL_checknumber(L,7))}};
    if (operation != "to" && operation != "from") return 0;
    window->m_transformers.emplace_back(makeUnique<CExpressiveTaskAnimation>(window,
        operation == "from" && !reversing ? target : current,
        operation == "to" ? target : window->getFullWindowBoundingBox(), duration,
        luaL_optnumber(L, 13, 0.8), luaL_optstring(L, 10, ""), color(L,11,"211f26"), color(L,12,"d0bcff")));
    g_pHyprRenderer->damageWindow(window);
    return 0;
}
int focusAnimation(lua_State* L) {
    const std::string address = luaL_checkstring(L, 1), id = luaL_checkstring(L, 2), profile = luaL_checkstring(L, 3);
    PHLWINDOW window;
    for (const auto& w : Desktop::windowState()->windows())
        if (w->m_isMapped && std::format("0x{:x}", reinterpret_cast<uintptr_t>(w.get())) == address && std::format("{:x}", w->m_stableID) == id) { window = w; break; }
    if (!window) { lua_pushboolean(L, false); return 1; }
    if (profile == "state") {
        auto focus = CStackFocusAnimation::find(window);
        if (!focus) { lua_pushnil(L); return 1; }
        lua_createtable(L, 0, 2);
        lua_pushnumber(L, focus->scale()); lua_setfield(L, -2, "scale");
        lua_pushinteger(L, focus->paints()); lua_setfield(L, -2, "paints");
        return 1;
    }
    for (const auto& w : Desktop::windowState()->windows()) CStackFocusAnimation::clear(w);
    if (profile == "off" || CExpressiveTaskAnimation::find(window)) { lua_pushboolean(L, false); return 1; }
    double stiffness = 280, damping = .68, amplitude = .095;
    if (profile == "standard") { stiffness = 380; damping = .90; amplitude = .055; }
    else if (profile == "heavy") { stiffness = 190; damping = .78; amplitude = .070; }
    else if (profile == "jelly") { stiffness = 320; damping = .42; amplitude = .12; }
    else if (profile != "expressive") { lua_pushboolean(L, false); return 1; }
    // The outgoing client remains below the newly focused client in the real
    // compositor order, so pointer and keyboard routing change immediately.
    // Its visible portions recede at the same time as the new window lifts.
    const std::string outgoingAddress = luaL_optstring(L, 4, ""), outgoingId = luaL_optstring(L, 5, "");
    for (const auto& other : Desktop::windowState()->windows()) {
        if (other != window && other->m_isMapped && !CExpressiveTaskAnimation::find(other) &&
            std::format("0x{:x}", reinterpret_cast<uintptr_t>(other.get())) == outgoingAddress &&
            std::format("{:x}", other->m_stableID) == outgoingId) {
            other->m_transformers.emplace_back(makeUnique<CStackFocusAnimation>(other, stiffness, damping, -amplitude * 0.65));
            g_pHyprRenderer->damageWindow(other);
            break;
        }
    }
    window->m_transformers.emplace_back(makeUnique<CStackFocusAnimation>(window, stiffness, damping, amplitude));
    g_pHyprRenderer->damageWindow(window);
    lua_pushboolean(L, true); return 1;
}

}
APICALL EXPORT std::string PLUGIN_API_VERSION() { return HYPRLAND_API_VERSION; }
APICALL EXPORT PLUGIN_DESCRIPTION_INFO PLUGIN_INIT(HANDLE handle) {
    if (std::string(__hyprland_api_get_hash()) != __hyprland_api_get_client_hash()) throw std::runtime_error("hics motion: compositor ABI mismatch");
    HyprlandAPI::addLuaFunction(handle,"hics_motion","animate_window",animate);
    HyprlandAPI::addLuaFunction(handle,"hics_motion","focus_animation",focusAnimation);
    fullscreenListener = Event::bus()->m_events.window.fullscreen.listen([](PHLWINDOW window) {
        if (window && Fullscreen::controller()->getFullscreenModes(window).internal == Fullscreen::FSMODE_FULLSCREEN) { CExpressiveTaskAnimation::clear(window); CStackFocusAnimation::clear(window); }
    });
    return {"hics-motion","Expressive dock window transitions","hics","1.0"};
}
APICALL EXPORT void PLUGIN_EXIT() {
    fullscreenListener.reset();
    for (const auto& window : Desktop::windowState()->windows()) { CExpressiveTaskAnimation::clear(window); CStackFocusAnimation::clear(window); }
}
