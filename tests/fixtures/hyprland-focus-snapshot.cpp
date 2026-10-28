// Disposable guest diagnostic. No hooks, listeners, focus changes or renderer.
#include <hyprland/src/plugins/PluginAPI.hpp>
#include <hyprland/src/managers/SeatManager.hpp>
#include <hyprland/src/managers/input/InputManager.hpp>
#include <hyprland/src/managers/SessionLockManager.hpp>
#include <hyprland/src/desktop/state/FocusState.hpp>
#include <hyprland/src/desktop/view/WLSurface.hpp>
#include <hyprland/src/desktop/view/Window.hpp>
#include <nlohmann/json.hpp>
#include <fstream>
#include <stdexcept>
#include <unistd.h>

APICALL EXPORT std::string PLUGIN_API_VERSION() { return HYPRLAND_API_VERSION; }
APICALL EXPORT PLUGIN_DESCRIPTION_INFO PLUGIN_INIT(HANDLE) {
    char hostname[128]{};
    if (getuid()!=1000 || gethostname(hostname,sizeof(hostname)-1) || std::string(hostname)!="hics-test")
        throw std::runtime_error("Diagnostic is restricted to the disposable guest");
    auto window = Desktop::focusState()->window();
    auto keyboard = g_pSeatManager->m_state.keyboardFocus.lock();
    auto pointer = g_pSeatManager->m_state.pointerFocus.lock();
    auto pointerView = pointer ? Desktop::View::CWLSurface::fromResource(pointer) : nullptr;
    auto pointerWindow = pointerView ? Desktop::View::CWindow::fromView(pointerView->view()) : nullptr;
    auto keyboardView = keyboard ? Desktop::View::CWLSurface::fromResource(keyboard) : nullptr;
    auto keyboardWindow = keyboardView ? Desktop::View::CWindow::fromView(keyboardView->view()) : nullptr;
    nlohmann::json data{{"windowPresent",bool(window)}, {"keyboardPresent",bool(keyboard)},
        {"pointerPresent",bool(pointer)}, {"keyboardOwnerMatchesWindow",keyboardWindow==window},
        {"pointerOwnerMatchesWindow",pointerWindow==window},
        {"constrained",g_pInputManager->isConstrained()}, {"seatGrab",bool(g_pSeatManager->m_seatGrab)},
        {"locked",g_pSessionLockManager->isSessionLocked()}, {"exclusiveLayers",g_pInputManager->m_exclusiveLSes.size()}};
    if (window) {
        data["class"] = window->m_class;
        data["keyboardResourceMatchesWindow"] = keyboard==window->resource();
        data["pointerResourceMatchesWindow"] = pointer==window->resource();
    }
    if (keyboardWindow) data["keyboardOwnerClass"] = keyboardWindow->m_class;
    if (pointerWindow) data["pointerOwnerClass"] = pointerWindow->m_class;
    std::ofstream file("/run/user/1000/hics-focus117.json");
    file << data.dump(2) << '\n';
    if (!file) throw std::runtime_error("Cannot save guest diagnostic");
    return {"hics-focus-snapshot-test","Guest-only read-only focus snapshot","hics tests","1"};
}
APICALL EXPORT void PLUGIN_EXIT() {}
