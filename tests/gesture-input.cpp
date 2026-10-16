// SPDX-License-Identifier: MIT
// Inject libinput-shaped events into an isolated compositor's real input path.
#include <hyprland/src/plugins/PluginAPI.hpp>
#include <hyprland/src/managers/input/InputManager.hpp>
#include <hyprland/src/managers/input/UnifiedWorkspaceSwipeGesture.hpp>
#include <hyprland/src/managers/eventLoop/EventLoopManager.hpp>
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
#include <chrono>
#include <filesystem>
#include <fstream>
extern "C" {
#include <lua.h>
#include <lauxlib.h>
}

static nlohmann::json lastSwipe;
static void sendEvent(const std::string& phase, uint32_t fingers, double x, double y, bool cancelled, uint32_t interval = 40) {
    static uint32_t time = 0;
    time += interval;
    if (phase == "begin") g_pInputManager->onSwipeBegin({.timeMs = time, .fingers = fingers});
    else if (phase == "update") g_pInputManager->onSwipeUpdate({.timeMs = time, .fingers = fingers, .delta = {x, y}});
    else if (phase == "end") g_pInputManager->onSwipeEnd({.timeMs = time, .cancelled = cancelled});
    const auto workspace = Desktop::focusState()->monitor()->m_activeWorkspace;
    lastSwipe = {{"phase", phase}, {"x", workspace->m_renderOffset->value().x}, {"y", workspace->m_renderOffset->value().y},
        {"style", workspace->m_renderOffset->getStyle()}, {"active", g_pUnifiedWorkspaceSwipe->isGestureInProgress()}};
}

static int send(lua_State* L) {
    const std::string phase = luaL_checkstring(L, 1);
    if (phase != "begin" && phase != "update" && phase != "end") return luaL_error(L, "Unknown swipe phase");
    sendEvent(phase, luaL_checkinteger(L, 2), luaL_optnumber(L, 3, 0), luaL_optnumber(L, 4, 0), lua_toboolean(L, 5));
    return 0;
}

// Replay is confined to the test compositor. It never creates a kernel input
// device, so the host desktop cannot receive a four-finger suspend gesture.
static SP<CEventLoopTimer> replayTimer;
struct Replay {
    bool active = false, cancelled = false;
    uint32_t fingers = 3;
    Vector2D total, previous;
    double duration = 1;
    std::chrono::steady_clock::time_point started;
    std::string trace, label;
} replay;

static void trace(const std::string& phase) {
    if (replay.trace.empty()) return;
    const auto value = nlohmann::json{{"phase", phase}, {"fingers", replay.fingers},
        {"x", replay.previous.x}, {"y", replay.previous.y}, {"label", replay.label},
        {"cancelled", replay.cancelled}, {"emulated", true}}.dump();
    { std::ofstream file(replay.trace + ".next"); file << value; }
    std::filesystem::rename(replay.trace + ".next", replay.trace);
}

static int play(lua_State* L) {
    if (replay.active) return luaL_error(L, "A swipe is already replaying");
    replay.fingers = luaL_checkinteger(L, 1);
    replay.total = {luaL_checknumber(L, 2), luaL_checknumber(L, 3)};
    replay.duration = luaL_checknumber(L, 4);
    if (replay.duration < .15 || replay.duration > 5) return luaL_error(L, "Swipe duration must be .15 to 5 seconds");
    replay.trace = luaL_checkstring(L, 5);
    replay.label = luaL_checkstring(L, 6);
    replay.cancelled = lua_toboolean(L, 7);
    replay.previous = {};
    replay.started = std::chrono::steady_clock::now();
    replay.active = true;
    sendEvent("begin", replay.fingers, 0, 0, false, 16);
    trace("begin");
    replayTimer->updateTimeout(std::chrono::milliseconds(16));
    return 0;
}

static int state(lua_State* L) {
    using Json = nlohmann::json;
    const auto monitor = Desktop::focusState()->monitor();
    const auto workspace = monitor->m_activeWorkspace;
    const auto algorithm = workspace->m_space->algorithm();
    const auto scrolling = dynamic_cast<Layout::Tiled::CScrollingAlgorithm*>(algorithm->tiledAlgo().get());
    Json result = {{"workspace", workspace->m_id}, {"tape", scrolling ? scrolling->normalizedTapeOffset() : 0},
        {"lastSwipe", lastSwipe}, {"replaying", replay.active},
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
    HyprlandAPI::addLuaFunction(handle, "gesture_input", "replay", play);
    replayTimer = makeShared<CEventLoopTimer>(std::nullopt, [](SP<CEventLoopTimer> timer, void*) {
        if (!replay.active) return;
        const double t = std::clamp(std::chrono::duration<double>(std::chrono::steady_clock::now() - replay.started).count() / replay.duration, 0.0, 1.0);
        const auto point = replay.total * (t * t * (3 - 2 * t));
        const auto delta = point - replay.previous;
        sendEvent("update", replay.fingers, delta.x, delta.y, false, 16);
        replay.previous = point;
        trace("update");
        if (t >= 1) {
            sendEvent("end", replay.fingers, 0, 0, replay.cancelled, 16);
            trace("end");
            replay.active = false;
        } else timer->updateTimeout(std::chrono::milliseconds(16));
    }, nullptr);
    g_pEventLoopManager->addTimer(replayTimer);
    return {"gesture-input", "Isolated trackpad regression fixture", "Hyprstack", "1"};
}
APICALL EXPORT void PLUGIN_EXIT() {
    if (replay.active) sendEvent("end", replay.fingers, 0, 0, true);
    g_pEventLoopManager->removeTimer(replayTimer);
    replayTimer.reset();
    replay.active = false;
}
