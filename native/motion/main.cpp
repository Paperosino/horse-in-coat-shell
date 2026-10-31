#include <hyprland/src/plugins/PluginAPI.hpp>
#include <hyprland/src/desktop/state/WindowState.hpp>
#include <hyprland/src/config/ConfigManager.hpp>
#include "task-animation.hpp"
#include "focus-animation.hpp"
#include <hyprland/src/event/EventBus.hpp>
#include <hyprland/src/managers/fullscreen/FullscreenController.hpp>
#include <hyprland/src/desktop/state/FocusState.hpp>
#include <hyprland/src/desktop/Workspace.hpp>
#include <hyprland/src/desktop/view/WLSurface.hpp>
#include <hyprland/src/render/pass/RendererHintsPassElement.hpp>
#include <hyprland/src/render/pass/SurfacePassElement.hpp>
#include <hyprland/src/render/decorations/DecorationPositioner.hpp>
extern "C" {
#include <lua.h>
#include <lauxlib.h>
}

namespace {
CHyprSignalListener fullscreenListener, handoffRender;
PHLWINDOWREF handoffFrom, handoffTo;
uint64_t handoffFrames = 0;
void clearHandoff() { handoffFrom.reset(); handoffTo.reset(); }
void renderHandoff(eRenderStage stage) {
    if (stage != RENDER_POST_WINDOWS) return;
    const auto from = handoffFrom.lock(), to = handoffTo.lock();
    if (!from || !to || !from->m_isMapped || !to->m_isMapped || from->isHidden() || to->isHidden() ||
        from->m_workspace != to->m_workspace || Desktop::focusState()->window() != to) { clearHandoff(); return; }
    const auto animation = CStackFocusAnimation::find(to);
    if (!animation || animation->progress() >= animation->peakTime()) { clearHandoff(); return; }
    const auto monitor = g_pHyprRenderer->m_renderData.pMonitor.lock();
    if (!monitor || from->m_monitor.lock() != monitor) return;
    // Only the composition order is temporarily changed. Hyprland has already
    // focused and raised the target for hit testing and keyboard delivery.
    ++handoffFrames;
    auto* renderer = g_pHyprRenderer.get();
    const auto surface = from->wlSurface();
    if (!surface || !surface->resource()) return;
    const auto now = Time::steadyNow();
    const auto offset = from->m_workspace && !from->m_pinned ? from->m_workspace->m_renderOffset->value() : Vector2D{};
    const auto position = from->position(Desktop::View::IGeometric::GEOMETRIC_CURRENT) + from->m_floatingOffset + offset;
    const auto size = from->size(Desktop::View::IGeometric::GEOMETRIC_CURRENT);
    const auto outgoing = CStackFocusAnimation::find(from);
    const double factor = outgoing ? outgoing->scale() : 1.0;
    const Vector2D origin = position - monitor->m_position;
    Render::SRenderModifData transform;
    transform.modifs.emplace_back(Render::SRenderModifData::RMOD_TYPE_SCALE, static_cast<float>(factor));
    transform.modifs.emplace_back(Render::SRenderModifData::RMOD_TYPE_TRANSLATE,
        (origin + size * 0.5) * (1.0 - factor) * monitor->m_scale);
    renderer->addPassElement(makeUnique<CRendererHintsPassElement>(CRendererHintsPassElement::SData{transform}));
    CSurfacePassElement::SRenderData data{monitor,now};
    data.pos = position; data.w = std::max(1.0,size.x); data.h = std::max(1.0,size.y); data.pWindow = from;
    data.alpha = from->alphaValue(Desktop::View::WINDOW_ALPHA_ACTIVE); data.fadeAlpha = 1;
    data.rounding = std::round(from->rounding()*monitor->m_scale); data.roundingPower = from->roundingPower();
    const auto oldWindow = renderer->m_renderData.currentWindow;
    renderer->m_renderData.currentWindow = from;
    Event::bus()->m_events.render.stage.emit(RENDER_PRE_WINDOW);
    g_pDecorationPositioner->onWindowUpdate(from);
    if (!from->m_X11DoesntWantBorders) for (const auto& deco : from->m_windowDecorations)
        if (deco->getDecorationLayer() == DECORATION_LAYER_BOTTOM || deco->getDecorationLayer() == DECORATION_LAYER_UNDER) deco->draw(monitor,1);
    surface->resource()->breadthfirst([&](SP<CWLSurfaceResource> child,const Vector2D& local,void*) {
        if (!child->m_current.texture || child->m_current.size.x < 1 || child->m_current.size.y < 1) return;
        data.surface=child; data.texture=child->m_current.texture; data.localPos=local; data.mainSurface=child==surface->resource();
        renderer->addPassElement(makeUnique<CSurfacePassElement>(data));
    },nullptr);
    if (!from->m_X11DoesntWantBorders) for (const auto& deco : from->m_windowDecorations)
        if (deco->getDecorationLayer() == DECORATION_LAYER_OVER) deco->draw(monitor,1);
    Event::bus()->m_events.render.stage.emit(RENDER_POST_WINDOW);
    renderer->m_renderData.currentWindow = oldWindow;
    renderer->addPassElement(makeUnique<CRendererHintsPassElement>(CRendererHintsPassElement::SData{Render::SRenderModifData{}}));
}

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
    if (operation == "to" || operation == "from") { clearHandoff(); CStackFocusAnimation::clear(window); }
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
        lua_pushboolean(L, handoffTo.lock() == window); lua_setfield(L, -2, "handoff");
        lua_pushinteger(L, handoffFrames); lua_setfield(L, -2, "handoffFrames");
        lua_pushnumber(L, focus->progress()); lua_setfield(L, -2, "elapsed");
        lua_pushnumber(L, focus->peakTime()); lua_setfield(L, -2, "peak");
        return 1;
    }
    clearHandoff();
    handoffFrames = 0;
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
    const auto accent = color(L, 6, "d0bcff");
    for (const auto& other : Desktop::windowState()->windows()) {
        if (other != window && other->m_isMapped && !CExpressiveTaskAnimation::find(other) &&
            std::format("0x{:x}", reinterpret_cast<uintptr_t>(other.get())) == outgoingAddress &&
            std::format("{:x}", other->m_stableID) == outgoingId) {
            handoffFrom = other;
            handoffTo = window;
            other->m_transformers.emplace_back(makeUnique<CStackFocusAnimation>(other, stiffness, damping, -amplitude * 0.65, accent));
            g_pHyprRenderer->damageWindow(other);
            break;
        }
    }
    window->m_transformers.emplace_back(makeUnique<CStackFocusAnimation>(window, stiffness, damping, amplitude, accent));
    g_pHyprRenderer->damageWindow(window);
    lua_pushboolean(L, true); return 1;
}

}
APICALL EXPORT std::string PLUGIN_API_VERSION() { return HYPRLAND_API_VERSION; }
APICALL EXPORT PLUGIN_DESCRIPTION_INFO PLUGIN_INIT(HANDLE handle) {
    if (std::string(__hyprland_api_get_hash()) != __hyprland_api_get_client_hash()) throw std::runtime_error("hics motion: compositor ABI mismatch");
    HyprlandAPI::addLuaFunction(handle,"hics_motion","animate_window",animate);
    HyprlandAPI::addLuaFunction(handle,"hics_motion","focus_animation",focusAnimation);
    handoffRender = Event::bus()->m_events.render.stage.listen(renderHandoff);
    fullscreenListener = Event::bus()->m_events.window.fullscreen.listen([](PHLWINDOW window) {
        if (window && Fullscreen::controller()->getFullscreenModes(window).internal == Fullscreen::FSMODE_FULLSCREEN) { CExpressiveTaskAnimation::clear(window); CStackFocusAnimation::clear(window); }
    });
    return {"hics-motion","Expressive dock window transitions","hics","1.0"};
}
APICALL EXPORT void PLUGIN_EXIT() {
    clearHandoff();
    handoffRender.reset();
    fullscreenListener.reset();
    for (const auto& window : Desktop::windowState()->windows()) { CExpressiveTaskAnimation::clear(window); CStackFocusAnimation::clear(window); }
}
