// Keep the Wayland seat, desktop focus and XWM activation in agreement.
#pragma once
#include <hyprland/src/managers/SeatManager.hpp>
#include <hyprland/src/managers/eventLoop/EventLoopManager.hpp>
#include <hyprland/src/managers/input/InputManager.hpp>
#include <hyprland/src/devices/IKeyboard.hpp>
#include <hyprland/src/managers/SessionLockManager.hpp>
#include <hyprland/src/desktop/state/FocusState.hpp>
#include <hyprland/src/desktop/view/WLSurface.hpp>
#include <hyprland/src/desktop/view/LayerSurface.hpp>
#include <hyprland/src/desktop/Workspace.hpp>
#include <hyprland/src/protocols/core/Compositor.hpp>
#include <hyprland/src/event/EventBus.hpp>
#include <hyprland/src/xwayland/XWayland.hpp>

namespace HicsKeyboardFocus {
inline CHyprSignalListener seatChanged, key;
inline UP<SEventLoopDoLaterLock> pendingRepair;
inline void repairFocus();
#ifndef NO_XWAYLAND
using Activate = void (*)(CXWM*, SP<CXWaylandSurface>, bool);
inline Activate activate = nullptr;
inline bool reconciling = false;
inline void syncXwm() {
    if (reconciling || !activate || !g_pSeatManager || !g_pXWayland || !g_pXWayland->m_wm || !g_pXWayland->m_server) return;
    const auto surface = g_pSeatManager->m_state.keyboardFocus.lock();
    const auto view = surface ? Desktop::View::CWLSurface::fromResource(surface) : nullptr;
    const auto window = view ? Desktop::View::CWindow::fromView(view->view()) : nullptr;
    reconciling = true;
    if (!surface || surface->client() != g_pXWayland->m_server->m_xwaylandClient) {
        // A layer is not a CWindow. The upstream XWM otherwise retains its
        // cached X11 target when the seat leaves for a shell popup, and can
        // suppress WM_TAKE_FOCUS when returning to that same application.
        activate(g_pXWayland->m_wm.get(), nullptr, false);
    } else if (window && window->m_isMapped && window->m_isX11 && !window->isX11OverrideRedirect() &&
        window == Desktop::focusState()->window())
        activate(g_pXWayland->m_wm.get(), window->m_xwaylandSurface.lock(), true);
    reconciling = false;
    // Let unmap/focus transitions finish before repairing a vacant seat.
    // WM_TAKE_FOCUS clients need this round trip before the first key arrives.
    if (!surface && !pendingRepair)
        pendingRepair = g_pEventLoopManager->doLaterLock([] {
            pendingRepair.reset();
            if (!g_pSeatManager->m_state.keyboardFocus.lock()) repairFocus();
        });
}
#endif
inline void repairFocus() {
    if (!g_pSeatManager ||
        g_pSessionLockManager->isSessionLocked() || !g_pInputManager->m_exclusiveLSes.empty() || g_pSeatManager->m_seatGrab) return;
    const auto window = Desktop::focusState()->window();
    if (!window || !window->m_isX11 || !window->m_isMapped || window->isHidden() || !window->m_workspace || !window->m_workspace->isVisible()) return;
    const auto target = window->resource();
    if (!target) return;
    const auto current = g_pSeatManager->m_state.keyboardFocus.lock();
    if (current == target) return;
    if (current) {
        const auto view = Desktop::View::CWLSurface::fromResource(current);
        const auto layer = view ? Desktop::View::CLayerSurface::fromView(view->view()) : nullptr;
        // Never steal from another app, a text field or an interactive popup.
        if (!layer || (Desktop::View::validMapped(layer) && layer->m_interactivity != 0)) return;
    }
    // fullWindowFocus can early-return on a cached desktop surface. Repair
    // the surface focus itself before this very key is forwarded to the seat.
    Desktop::focusState()->rawSurfaceFocus(target, window);
}
inline void repairBeforeKey(IKeyboard::SKeyEvent event, Event::SCallbackInfo&) {
    if (event.state == WL_KEYBOARD_KEY_STATE_PRESSED) repairFocus();
}
inline void install(HANDLE handle) {
#ifndef NO_XWAYLAND
    for (const auto& symbol : HyprlandAPI::findFunctionsByName(handle, "activateSurface")) {
        if (!symbol.demangled.starts_with("CXWM::activateSurface(")) continue;
        // Pinned public symbol lookup; no additional inline hook or private
        // field access is needed to invalidate XWM's stale activation cache.
        activate = reinterpret_cast<Activate>(symbol.address);
        break;
    }
    seatChanged = g_pSeatManager->m_events.keyboardFocusChange.listen([] { syncXwm(); });
#endif
    key = Event::bus()->m_events.input.keyboard.key.listen(repairBeforeKey);
}
inline void remove() {
    key.reset(); seatChanged.reset(); pendingRepair.reset();
#ifndef NO_XWAYLAND
    activate = nullptr;
#endif
}
}
