// One protocol-based decision for shell headers. Never inspect app names,
// pixels, shadow margins, opaque regions or move/resize requests.
#pragma once
#include <hyprland/src/defines.hpp>
#include <hyprland/src/plugins/PluginAPI.hpp>
#include <string_view>

namespace hics::decoration {
enum class Mode { Unknown, Server, Client, None };
struct Decision {
    Mode mode = Mode::Unknown;
    std::string_view source = "unavailable";
    bool titlebar = false;
    double height = 0;
};
struct Diagnostics { size_t xdgSurfaces, kdeSurfaces, xdgBindings, kdeBindings, x11Surfaces, pendingX11; };
Diagnostics diagnostics();
Decision evaluate(PHLWINDOW window);
void observe(PHLWINDOW window);
void install(HANDLE handle);
void remove(HANDLE handle);
const char* name(Mode mode);
}
