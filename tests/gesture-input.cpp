// SPDX-License-Identifier: MIT
// Inject libinput-shaped events into an isolated compositor's real input path.
#include <hyprland/src/plugins/PluginAPI.hpp>
#include <hyprland/src/managers/input/InputManager.hpp>
#include <hyprland/src/managers/input/UnifiedWorkspaceSwipeGesture.hpp>
#include <hyprland/src/desktop/state/FocusState.hpp>
#include <hyprland/src/desktop/state/WindowState.hpp>
#include <hyprland/src/desktop/view/Window.hpp>
#include <hyprland/src/desktop/Workspace.hpp>
#include <hyprland/src/output/Monitor.hpp>
#include <hyprland/src/state/WorkspaceState.hpp>
#include <hyprland/src/layout/space/Space.hpp>
#include <hyprland/src/layout/algorithm/Algorithm.hpp>
#include <hyprland/src/layout/algorithm/tiled/scrolling/ScrollingAlgorithm.hpp>
#include <nlohmann/json.hpp>
extern "C" {
#include <lua.h>
#include <lauxlib.h>
}

static nlohmann::json lastSwipe;
static int send(lua_State* L) {
    static uint32_t time = 0;
    time += 40;
    const std::string phase = luaL_checkstring(L, 1);
    const auto fingers = static_cast<uint32_t>(luaL_checkinteger(L, 2));
    if (phase == "begin") g_pInputManager->onSwipeBegin({.timeMs = time, .fingers = fingers});
    else if (phase == "update") g_pInputManager->onSwipeUpdate({.timeMs = time, .fingers = fingers,
        .delta = {luaL_checknumber(L, 3), luaL_checknumber(L, 4)}});
    else if (phase == "end") g_pInputManager->onSwipeEnd({.timeMs = time, .cancelled = static_cast<bool>(lua_toboolean(L, 5))});
    else return luaL_error(L, "Unknown swipe phase");
    const auto workspace = Desktop::focusState()->monitor()->m_activeWorkspace;
    lastSwipe = {{"phase", phase}, {"x", workspace->m_renderOffset->value().x}, {"y", workspace->m_renderOffset->value().y},
        {"style", workspace->m_renderOffset->getStyle()}, {"active", g_pUnifiedWorkspaceSwipe->isGestureInProgress()}};
    return 0;
}

static int state(lua_State* L) {
    using Json = nlohmann::json;
    const auto monitor = Desktop::focusState()->monitor();
    const auto workspace = monitor->m_activeWorkspace;
    const auto algorithm = workspace->m_space->algorithm();
    const auto scrolling = dynamic_cast<Layout::Tiled::CScrollingAlgorithm*>(algorithm->tiledAlgo().get());
    Json result = {{"workspace", workspace->m_id}, {"tape", scrolling ? scrolling->normalizedTapeOffset() : 0}, {"lastSwipe", lastSwipe},
        {"windows", Json::object()}, {"workspaces", Json::object()}};
    for (const auto& w : Desktop::windowState()->windows()) {
        if (!w->m_isMapped) continue;
        const auto position = w->positionAnimation()->value(), goal = w->positionAnimation()->goal();
        result["windows"][w->m_title] = {{"position", {position.x, position.y}}, {"goal", {goal.x, goal.y}},
            {"workspace", w->m_workspace->m_id}};
    }
    for (const auto& weak : State::workspaceState()->workspaces()) {
        const auto ws = weak.lock();
        if (!ws || ws->m_monitor != monitor || ws->m_isSpecialWorkspace) continue;
        result["workspaces"][std::to_string(ws->m_id)] = {{"y", ws->m_renderOffset->value().y},
            {"alpha", ws->m_alpha->value()}, {"rendered", ws->m_forceRendering}};
    }
    const auto value = result.dump();
    lua_pushlstring(L, value.data(), value.size());
    return 1;
}

APICALL EXPORT std::string PLUGIN_API_VERSION() { return HYPRLAND_API_VERSION; }
APICALL EXPORT PLUGIN_DESCRIPTION_INFO PLUGIN_INIT(HANDLE handle) {
    if (std::string(__hyprland_api_get_hash()) != __hyprland_api_get_client_hash()) throw std::runtime_error("ABI mismatch");
    HyprlandAPI::addLuaFunction(handle, "gesture_input", "send", send);
    HyprlandAPI::addLuaFunction(handle, "gesture_input", "state", state);
    return {"gesture-input", "Isolated trackpad regression fixture", "Hyprstack", "1"};
}
APICALL EXPORT void PLUGIN_EXIT() {}
