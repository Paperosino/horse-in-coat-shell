#include "decoration-policy.hpp"
#include "barDeco.hpp"
#include "globals.hpp"
#include <hyprland/src/Compositor.hpp>
#include <hyprland/src/desktop/state/WindowState.hpp>
#include <hyprland/src/desktop/view/Window.hpp>
#include <hyprland/src/desktop/view/WLSurface.hpp>
#include <hyprland/src/desktop/rule/windowRule/WindowRuleApplicator.hpp>
#include <hyprland/src/protocols/XDGDecoration.hpp>
#include <hyprland/src/protocols/XDGShell.hpp>
#include <hyprland/src/protocols/ServerDecorationKDE.hpp>
#include <hyprland/src/protocols/core/Compositor.hpp>
#include <hyprland/src/plugins/HookSystem.hpp>
#include <hyprland/src/managers/eventLoop/EventLoopManager.hpp>
#include <hyprland/src/managers/fullscreen/FullscreenController.hpp>
#include <hyprland/src/xwayland/XWayland.hpp>
#include <hyprland/src/event/EventBus.hpp>
#include <algorithm>
#include <array>
#include <cstdlib>
#include <memory>
#include <unordered_map>
#ifndef NO_XWAYLAND
#include <xcb/xcbext.h>
#endif

namespace hics::decoration {
namespace {
struct Negotiation {
    WP<CXDGSurfaceResource> surface;
    const void* owner = nullptr;
    Mode applied = Mode::Unknown, pending = Mode::Unknown;
    uint32_t serial = 0;
    bool acknowledged = false, dirty = false;
    CHyprSignalListener ack, commit, destroy;
};
// xdg-decoration takes precedence over the deprecated KDE protocol.
std::unordered_map<CXDGSurfaceResource*, std::unique_ptr<Negotiation>> xdg;
struct Legacy {
    WP<CWLSurfaceResource> surface;
    const void* owner = nullptr;
    Mode mode = Mode::Unknown, pending = Mode::Unknown;
    bool dirty = false;
    CHyprSignalListener commit, destroy;
};
std::unordered_map<CWLSurfaceResource*, std::unique_ptr<Legacy>> kde;
std::array<CFunctionHook*, 6> hooks{};
struct ResourceLifetime {
    wl_listener listener{};
    void* key = nullptr;
    bool legacy = false;
    ResourceLifetime() { wl_list_init(&listener.link); }
    ~ResourceLifetime() { wl_list_remove(&listener.link); }
};
using XdgHandler = std::function<void(CZxdgToplevelDecorationV1*, zxdgToplevelDecorationV1Mode)>;
struct XdgBinding { WP<CZxdgToplevelDecorationV1> resource; CXDGDecoration* owner = nullptr; XdgHandler original; std::unique_ptr<ResourceLifetime> lifetime; };
std::unordered_map<CZxdgToplevelDecorationV1*, XdgBinding> xdgBindings;
using KdeHandler = std::function<void(COrgKdeKwinServerDecoration*, uint32_t)>;
struct KdeBinding { WP<COrgKdeKwinServerDecoration> resource; CServerDecorationKDE* owner = nullptr; KdeHandler original; std::unique_ptr<ResourceLifetime> lifetime; };
std::unordered_map<COrgKdeKwinServerDecoration*, KdeBinding> kdeBindings;
void resourceDestroyed(wl_listener* listener, void*) {
    auto* lifetime = reinterpret_cast<ResourceLifetime*>(listener);
    // Only compare owner identities: its C++ destructor may already be in
    // progress. The pending change applies to the next surface commit.
    if (lifetime->legacy) {
        auto* key = static_cast<COrgKdeKwinServerDecoration*>(lifetime->key);
        const auto it = kdeBindings.find(key);
        if (it == kdeBindings.end()) return;
        for (const auto& [surface, state] : kde) if (state->owner == it->second.owner) {
            state->owner = nullptr; state->pending = Mode::Unknown; state->dirty = true;
        }
        kdeBindings.erase(it);
    } else {
        auto* key = static_cast<CZxdgToplevelDecorationV1*>(lifetime->key);
        const auto it = xdgBindings.find(key);
        if (it == xdgBindings.end()) return;
        for (const auto& [surface, state] : xdg) if (state->owner == it->second.owner) {
            state->owner = nullptr; state->pending = Mode::Unknown;
            state->acknowledged = true; state->dirty = true;
        }
        xdgBindings.erase(it);
    }
}
std::unique_ptr<ResourceLifetime> watchResource(wl_resource* resource, void* key, bool legacy) {
    auto life = std::make_unique<ResourceLifetime>();
    life->key = key; life->legacy = legacy; life->listener.notify = resourceDestroyed;
    wl_resource_add_destroy_listener(resource, &life->listener);
    return life;
}
CHyprSignalListener closed;

void refresh(PHLWINDOW window) {
    if (!window || !window->m_isMapped || !g_pGlobalState) return;
    for (const auto& bar : g_pGlobalState->bars)
        if (bar && bar->getOwner() == window) bar->updateRules();
    window->updateWindowDecos();
}
PHLWINDOW windowFor(SP<CWLSurfaceResource> surface) {
    const auto wl = surface ? Desktop::View::CWLSurface::fromResource(surface) : nullptr;
    return wl ? Desktop::View::CWindow::fromView(wl->view()) : nullptr;
}
void configure(CXDGDecoration* decoration, Mode mode) {
    const auto top = CXDGToplevelResource::fromResource(decoration->toplevelResource());
    const auto surface = top ? top->m_owner.lock() : nullptr;
    if (!surface) return;
    auto& record = xdg[surface.get()];
    if (!record) {
        record = std::make_unique<Negotiation>();
        auto* state = record.get();
        state->surface = surface;
        state->ack = surface->m_events.ack.listen([state](uint32_t serial) {
            // Serial wrap is legal. Difference comparison is safe within the
            // bounded outstanding configure window.
            if (state->dirty && static_cast<int32_t>(serial - state->serial) >= 0) state->acknowledged = true;
        });
        state->commit = surface->m_events.commit.listen([state] {
            if (!state->dirty || !state->acknowledged) return;
            state->dirty = false;
            if (state->applied == state->pending) return;
            state->applied = state->pending;
            if (const auto surface = state->surface.lock()) refresh(windowFor(surface->m_surface.lock()));
        });
        state->destroy = surface->m_events.destroy.listen([key = surface.get()] { xdg.erase(key); });
    }
    record->owner = decoration;
    record->pending = mode;
    record->serial = surface->scheduleConfigure();
    record->acknowledged = false;
    record->dirty = true;
}
using XdgSetter = void (*)(CZxdgToplevelDecorationV1*, XdgHandler&&);
void xdgSetter(CZxdgToplevelDecorationV1* resource, XdgHandler&& handler) {
    // Preserve the compositor-owned callback so plugin teardown can restore
    // it. No lambda implemented in this DSO may survive its unload.
    xdgBindings[resource].original = handler;
    reinterpret_cast<XdgSetter>(hooks[1]->m_original)(resource, std::move(handler));
}
void xdgSend(CZxdgToplevelDecorationV1* resource, zxdgToplevelDecorationV1Mode mode) {
    if (const auto it = xdgBindings.find(resource); it != xdgBindings.end() && it->second.owner)
        configure(it->second.owner, mode == ZXDG_TOPLEVEL_DECORATION_V1_MODE_SERVER_SIDE ? Mode::Server : Mode::Client);
    reinterpret_cast<void (*)(CZxdgToplevelDecorationV1*, zxdgToplevelDecorationV1Mode)>(hooks[2]->m_original)(resource, mode);
}
void xdgConstruct(CXDGDecoration* owner, SP<CZxdgToplevelDecorationV1> resource, wl_resource* top) {
    reinterpret_cast<void (*)(CXDGDecoration*, SP<CZxdgToplevelDecorationV1>, wl_resource*)>(hooks[0]->m_original)(owner, resource, top);
    if (!resource->resource()) return;
    auto& binding = xdgBindings[resource.get()];
    binding.resource = resource; binding.owner = owner;
    binding.lifetime = watchResource(resource->resource(), resource.get(), false);
    configure(owner, owner->mostRecentlySent == ZXDG_TOPLEVEL_DECORATION_V1_MODE_SERVER_SIDE ? Mode::Server : Mode::Client);
    XdgHandler handler = [owner](CZxdgToplevelDecorationV1* resource, zxdgToplevelDecorationV1Mode mode) {
        if (mode != ZXDG_TOPLEVEL_DECORATION_V1_MODE_CLIENT_SIDE && mode != ZXDG_TOPLEVEL_DECORATION_V1_MODE_SERVER_SIDE) {
            // Keep the pinned compositor's handling of unknown enum values.
            if (const auto it = xdgBindings.find(resource); it != xdgBindings.end()) it->second.original(resource, mode);
            return;
        }
        owner->mostRecentlyRequested = mode;
        resource->sendConfigure(mode);
        owner->mostRecentlySent = mode;
    };
    reinterpret_cast<XdgSetter>(hooks[1]->m_original)(resource.get(), std::move(handler));
}
void legacyMode(CServerDecorationKDE* decoration, uint32_t mode) {
    const auto surface = decoration->m_surf;
    if (!surface) return;
    auto& record = kde[surface.get()];
    if (!record) {
        record = std::make_unique<Legacy>();
        auto* state = record.get();
        state->surface = surface;
        state->commit = surface->m_events.commit.listen([state] {
            if (!state->dirty) return;
            state->dirty = false;
            if (state->mode == state->pending) return;
            state->mode = state->pending;
            refresh(windowFor(state->surface.lock()));
        });
        state->destroy = surface->m_events.destroy.listen([key = surface.get()] { kde.erase(key); });
    }
    record->owner = decoration;
    record->pending = mode == 2 ? Mode::Server : mode == 1 ? Mode::Client : Mode::None;
    record->dirty = true;
}
using KdeSetter = void (*)(COrgKdeKwinServerDecoration*, KdeHandler&&);
void kdeSetter(COrgKdeKwinServerDecoration* resource, KdeHandler&& handler) {
    kdeBindings[resource].original = handler;
    reinterpret_cast<KdeSetter>(hooks[4]->m_original)(resource, std::move(handler));
}
void kdeSend(COrgKdeKwinServerDecoration* resource, uint32_t mode) {
    if (const auto it = kdeBindings.find(resource); it != kdeBindings.end() && it->second.owner)
        legacyMode(it->second.owner, mode);
    reinterpret_cast<void (*)(COrgKdeKwinServerDecoration*, uint32_t)>(hooks[5]->m_original)(resource, mode);
}
void kdeConstruct(CServerDecorationKDE* owner, SP<COrgKdeKwinServerDecoration> resource, SP<CWLSurfaceResource> surface) {
    reinterpret_cast<void (*)(CServerDecorationKDE*, SP<COrgKdeKwinServerDecoration>, SP<CWLSurfaceResource>)>(hooks[3]->m_original)(owner, resource, surface);
    if (!resource->resource()) return;
    auto& binding = kdeBindings[resource.get()];
    binding.resource = resource; binding.owner = owner;
    binding.lifetime = watchResource(resource->resource(), resource.get(), true);
    legacyMode(owner, owner->m_mostRecentlySent);
    KdeHandler handler = [owner](COrgKdeKwinServerDecoration* resource, uint32_t mode) {
        if (mode > 2) {
            if (const auto it = kdeBindings.find(resource); it != kdeBindings.end()) it->second.original(resource, mode);
            return;
        }
        // Legacy clients may echo the configured mode. Do not initiate an
        // endless mode/configure loop when nothing changed.
        if (owner->m_mostRecentlyRequested == mode && owner->m_mostRecentlySent == mode) return;
        owner->m_mostRecentlyRequested = mode;
        resource->sendMode(mode);
        owner->m_mostRecentlySent = mode;
    };
    reinterpret_cast<KdeSetter>(hooks[4]->m_original)(resource.get(), std::move(handler));
}

#ifndef NO_XWAYLAND
struct Motif {
    WP<CXWaylandSurface> surface;
    // No property, invalid property, or no DECORATIONS flag means default SSD.
    std::optional<bool> title;
    uint64_t revision = 0;
    CHyprSignalListener destroy;
};
std::unordered_map<CXWaylandSurface*, std::unique_ptr<Motif>> motif;
struct Pending { WP<CXWaylandSurface> surface; unsigned sequence; uint64_t revision; };
std::vector<Pending> pending;
xcb_connection_t* xConnection = nullptr;
wl_event_source* xSource = nullptr;
CFunctionHook* xRead = nullptr;
UP<SEventLoopDoLaterLock> xDrain;
void eraseMotif(CXWaylandSurface* key) {
    std::erase_if(pending, [key](const auto& item) {
        const auto surface = item.surface.lock();
        if (surface && surface.get() != key) return false;
        if (xConnection) xcb_discard_reply(xConnection, item.sequence);
        return true;
    });
    motif.erase(key);
}
Motif& motifFor(SP<CXWaylandSurface> surface) {
    auto& cache = motif[surface.get()];
    if (!cache) {
        cache = std::make_unique<Motif>();
        cache->surface = surface;
        // Some helper/tooltip windows never map, so window.close alone is
        // insufficient to bound the cache's lifetime.
        cache->destroy = surface->m_events.destroy.listen([key = surface.get()] { eraseMotif(key); });
    }
    return *cache;
}

std::optional<bool> parseMotif(xcb_get_property_reply_t* reply) {
    if (!reply || reply->format != 32 || reply->type == XCB_ATOM_NONE || xcb_get_property_value_length(reply) < 12) return std::nullopt;
    const auto data = static_cast<uint32_t*>(xcb_get_property_value(reply));
    if (!(data[0] & (1U << 1))) return std::nullopt;
    const bool all = data[2] & 1U, title = data[2] & (1U << 3);
    // MWM_DECOR_ALL makes the remaining bits exclusions.
    return all ? !title : title;
}
void received(SP<CXWaylandSurface> surface, xcb_get_property_reply_t* reply) {
    if (!surface) return;
    const auto title = parseMotif(reply);
    auto& cache = motifFor(surface);
    const bool changed = cache.revision == 0 || cache.title != title;
    cache.title = title;
    ++cache.revision;
    if (changed) refresh(windowFor(surface->m_surface.lock()));
}
void readProp(CXWM* wm, SP<CXWaylandSurface> surface, uint32_t atom, xcb_get_property_reply_t* reply) {
    reinterpret_cast<void (*)(CXWM*, SP<CXWaylandSurface>, uint32_t, xcb_get_property_reply_t*)>(xRead->m_original)(wm, surface, atom, reply);
    const auto found = HYPRATOMS.find("_MOTIF_WM_HINTS");
    if (found != HYPRATOMS.end() && found->second == atom) received(surface, reply);
}
void disconnectX() {
    xDrain.reset();
    if (xSource) wl_event_source_remove(xSource);
    xSource = nullptr;
    if (xConnection) xcb_disconnect(xConnection);
    xConnection = nullptr;
    pending.clear();
}
int drainX(int, uint32_t mask, void*) {
    if (!xConnection) return 0;
    if (mask & (WL_EVENT_HANGUP | WL_EVENT_ERROR) || xcb_connection_has_error(xConnection)) { disconnectX(); return 0; }
    // Never wait for replies on the compositor thread. One request per map;
    // later property changes reuse the reply already read by Hyprland's XWM.
    while (auto* event = xcb_poll_for_event(xConnection)) std::free(event);
    for (auto it = pending.begin(); it != pending.end();) {
        void* reply = nullptr;
        xcb_generic_error_t* error = nullptr;
        if (!xcb_poll_for_reply(xConnection, it->sequence, &reply, &error)) { ++it; continue; }
        const auto surface = it->surface.lock();
        const auto revision = it->revision;
        it = pending.erase(it);
        const auto current = surface ? motif.find(surface.get()) : motif.end();
        if (current != motif.end() && current->second->revision == revision)
            received(surface, static_cast<xcb_get_property_reply_t*>(reply));
        std::free(reply); std::free(error);
    }
    return 0;
}
#endif
} // namespace

const char* name(Mode mode) {
    switch (mode) { case Mode::Server: return "server"; case Mode::Client: return "client"; case Mode::None: return "none"; default: return "unknown"; }
}
Diagnostics diagnostics() {
    return {xdg.size(), kde.size(), xdgBindings.size(), kdeBindings.size(),
#ifndef NO_XWAYLAND
        motif.size(), pending.size()
#else
        0, 0
#endif
    };
}
Decision evaluate(PHLWINDOW window) {
    Decision result;
    if (!window) return result;
    if (window->m_xdgSurface && window->m_xdgSurface->m_popup) return {Mode::None, "popup-role"};
    if (window->isX11OverrideRedirect() || window->m_X11DoesntWantBorders) return {Mode::None, "unmanaged-role"};
    if (!window->m_ruleApplicator->decorate().valueOrDefault()) return {Mode::None, "decoration-rule"};
    if (g_pGlobalState) {
        const auto& props = window->m_ruleApplicator->m_otherProps.props;
        if (const auto it = props.find(g_pGlobalState->nobarRuleIdx); it != props.end()) {
            const auto& value = it->second->effect;
            const bool hidden = value == "true" || value == "1" || value == "yes" || value == "on";
            result = {hidden ? Mode::None : Mode::Server, hidden ? "user-hide" : "user-show"};
            result.titlebar = !hidden;
        } else if (window->m_isX11) {
#ifndef NO_XWAYLAND
            const auto it = motif.find(window->m_xwaylandSurface.get());
            const bool title = it == motif.end() || it->second->title.value_or(true);
            result = {title ? Mode::Server : Mode::Client, it != motif.end() && it->second->title.has_value() ? "motif-hints" : "x11-default"};
            result.titlebar = title;
#endif
        } else {
            const auto top = window->m_xdgSurface.lock();
            const auto surface = window->resource();
            const auto negotiated = top ? xdg.find(top.get()) : xdg.end();
            const auto legacy = surface ? kde.find(surface.get()) : kde.end();
            if (negotiated != xdg.end() && negotiated->second->applied != Mode::Unknown)
                result = {negotiated->second->applied, "xdg-decoration"};
            else if (legacy != kde.end() && legacy->second->mode != Mode::Unknown)
                result = {legacy->second->mode, "kde-decoration"};
            else result = {Mode::Client, "wayland-self-decoration"};
            result.titlebar = result.mode == Mode::Server;
        }
        if (result.titlebar && g_pGlobalState->config.enabled && g_pGlobalState->config.enabled->value() &&
            Fullscreen::controller()->getFullscreenModes(window).internal != Fullscreen::FSMODE_FULLSCREEN)
            result.height = std::max<int64_t>(0, g_pGlobalState->config.barHeight->value());
    }
    return result;
}
void observe(PHLWINDOW window) {
#ifndef NO_XWAYLAND
    const auto surface = window && window->m_isX11 ? window->m_xwaylandSurface.lock() : nullptr;
    if (!surface || window->isX11OverrideRedirect()) return;
    if (const auto it = motif.find(surface.get()); it != motif.end()) {
        if (it->second->surface.lock() == surface) return;
        motif.erase(it);
    }
    if (xConnection && xcb_connection_has_error(xConnection)) disconnectX();
    if (!xConnection) {
        xConnection = xcb_connect(nullptr, nullptr);
        if (!xConnection || xcb_connection_has_error(xConnection)) { disconnectX(); return; }
        xSource = wl_event_loop_add_fd(g_pCompositor->m_wlEventLoop, xcb_get_file_descriptor(xConnection), WL_EVENT_READABLE, drainX, nullptr);
        if (!xSource) { disconnectX(); return; }
    }
    const auto found = HYPRATOMS.find("_MOTIF_WM_HINTS");
    if (found == HYPRATOMS.end()) return;
    motifFor(surface);
    const auto cookie = xcb_get_property(xConnection, false, surface->m_xID, found->second, XCB_ATOM_ANY, 0, 5);
    pending.push_back({surface, cookie.sequence, 0});
    xcb_flush(xConnection);
    // libxcb may have buffered a reply while flushing; drain once at idle,
    // then exclusively on fd readiness. There is no polling timer.
    xDrain = g_pEventLoopManager->doLaterLock([] { drainX(0, 0, nullptr); });
#endif
}
void remove(HANDLE handle) {
#ifndef NO_XWAYLAND
    disconnectX();
    if (xRead) HyprlandAPI::removeFunctionHook(handle, xRead);
    xRead = nullptr;
    motif.clear();
#endif
    closed.reset();
    for (auto& [key, binding] : xdgBindings)
        if (const auto resource = binding.resource.lock(); resource && hooks[1])
            reinterpret_cast<XdgSetter>(hooks[1]->m_original)(resource.get(), std::move(binding.original));
    for (auto& [key, binding] : kdeBindings)
        if (const auto resource = binding.resource.lock(); resource && hooks[4])
            reinterpret_cast<KdeSetter>(hooks[4]->m_original)(resource.get(), std::move(binding.original));
    xdgBindings.clear(); kdeBindings.clear();
    for (auto& hook : hooks) { if (hook) HyprlandAPI::removeFunctionHook(handle, hook); hook = nullptr; }
    xdg.clear(); kde.clear();
}
void install(HANDLE handle) {
    const auto hook = [&](const char* symbol, const char* prefix, void* replacement) {
        const auto functions = HyprlandAPI::findFunctionsByName(handle, symbol);
        const auto found = std::ranges::find_if(functions, [&](const auto& fn) { return fn.demangled.starts_with(prefix); });
        if (found == functions.end()) throw std::runtime_error(std::string("hics: missing decoration symbol ") + prefix);
        auto* result = HyprlandAPI::createFunctionHook(handle, found->address, replacement);
        if (!result || !result->hook()) { if (result) HyprlandAPI::removeFunctionHook(handle, result); throw std::runtime_error("hics: cannot install decoration policy"); }
        return result;
    };
    try {
        hooks[0] = hook("CXDGDecoration", "CXDGDecoration::CXDGDecoration(", reinterpret_cast<void*>(xdgConstruct));
        hooks[1] = hook("setSetMode", "CZxdgToplevelDecorationV1::setSetMode(", reinterpret_cast<void*>(xdgSetter));
        hooks[2] = hook("sendConfigure", "CZxdgToplevelDecorationV1::sendConfigure(", reinterpret_cast<void*>(xdgSend));
        hooks[3] = hook("CServerDecorationKDE", "CServerDecorationKDE::CServerDecorationKDE(", reinterpret_cast<void*>(kdeConstruct));
        hooks[4] = hook("setRequestMode", "COrgKdeKwinServerDecoration::setRequestMode(", reinterpret_cast<void*>(kdeSetter));
        hooks[5] = hook("sendMode", "COrgKdeKwinServerDecoration::sendMode(", reinterpret_cast<void*>(kdeSend));
#ifndef NO_XWAYLAND
        xRead = hook("readProp", "CXWM::readProp(", reinterpret_cast<void*>(readProp));
        closed = Event::bus()->m_events.window.close.listen([](PHLWINDOW window) {
            const auto surface = window->m_xwaylandSurface.lock();
            if (!surface) return;
            eraseMotif(surface.get());
        });
#endif
    } catch (...) { remove(handle); throw; }
}
} // namespace hics::decoration
