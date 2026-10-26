// Isolated-test fault injection only; never part of an installed plugin.
#include <hyprland/src/plugins/PluginAPI.hpp>
#include <hyprland/src/managers/SeatManager.hpp>
#include <hyprland/src/desktop/state/FocusState.hpp>
extern "C" {
#include <lua.h>
}
APICALL EXPORT std::string PLUGIN_API_VERSION() { return HYPRLAND_API_VERSION; }
APICALL EXPORT PLUGIN_DESCRIPTION_INFO PLUGIN_INIT(HANDLE handle) {
    HyprlandAPI::addLuaFunction(handle, "hics_input_test", "drop_seat", [](lua_State*) -> int {
        g_pSeatManager->setKeyboardFocus(nullptr);
        return 0;
    });
    return {"hics-input-test", "Private test focus fault", "hics", "1"};
}
APICALL EXPORT void PLUGIN_EXIT() {}
