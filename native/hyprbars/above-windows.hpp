#pragma once
#include "globals.hpp"
#include <hyprland/src/desktop/state/WindowState.hpp>
#include <hyprland/src/event/EventBus.hpp>
#include <hyprland/src/managers/fullscreen/FullscreenController.hpp>
#include <hyprland/src/plugins/HookSystem.hpp>
#include <unordered_map>
#include <dlfcn.h>

namespace hics::above {
inline std::unordered_map<uint64_t, PHLWINDOWREF> windows;
inline CFunctionHook* hook = nullptr;
inline CHyprSignalListener closed;
using Raise = void (*)(Desktop::CWindowState*, PHLWINDOW);

// Native pointer clicks raise after focus callbacks. Enforce the same order
// at the public raise operation, rather than racing a later Lua focus event.
inline void raised(Desktop::CWindowState* state, PHLWINDOW window) {
    const auto original = reinterpret_cast<Raise>(hook->m_original);
    original(state, window);
    if (!window || windows.empty() || !g_pGlobalState || !g_pGlobalState->config.enabled->value()
        || windows.contains(window->m_stableID)
        || Fullscreen::controller()->getFullscreenModes(window).internal == Fullscreen::FSMODE_FULLSCREEN) return;
    for (auto it = windows.begin(); it != windows.end();) {
        const auto above = it->second.lock();
        if (!above || above->m_stableID != it->first) { it = windows.erase(it); continue; }
        ++it;
        if (above->m_isMapped && !above->isHidden() && above->m_workspace == window->m_workspace)
            original(state, above);
    }
}
inline bool set(PHLWINDOW window, bool enabled) {
    if (!window || !window->m_isMapped || !hook) return false;
    if (enabled) windows[window->m_stableID] = window;
    else windows.erase(window->m_stableID);
    Desktop::windowState()->raise(window);
    return true;
}
inline void remove(HANDLE handle) {
    closed.reset();
    if (hook) HyprlandAPI::removeFunctionHook(handle,hook);
    hook=nullptr;
    windows.clear();
}
inline void install(HANDLE handle) {
    // Exported ABI of the pinned Hyprland 0.56.2. Resolve it directly:
    // findFunctionsByName pairs separate nm/demangler output by line number.
    const auto address = dlsym(RTLD_DEFAULT,
        "_ZN7Desktop12CWindowState5raiseEN9Hyprutils6Memory14CSharedPointerINS_4View7CWindowEEE");
    if (!address) throw std::runtime_error("hics: missing pinned window raise symbol");
    hook=HyprlandAPI::createFunctionHook(handle,address,reinterpret_cast<void*>(raised));
    if (!hook || !hook->hook()) { remove(handle); throw std::runtime_error("hics: cannot install window stacking order"); }
    closed=Event::bus()->m_events.window.close.listen([](PHLWINDOW window){if(window)windows.erase(window->m_stableID);});
}
}
