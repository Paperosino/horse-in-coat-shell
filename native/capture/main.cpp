// Hyprland 0.56.2: complete requested window exports outside native output
// coordinates. Canvas windows remain mapped there while the camera shows them.
#include <algorithm>
#include <any>
#include <array>
#include <chrono>
#include <functional>
#include <map>
#include <memory>
#include <optional>
#include <span>
#include <sstream>
#include <string>
#include <unordered_map>
#include <variant>
#include <vector>
#include <hyprland/src/plugins/PluginAPI.hpp>
#include <hyprland/src/render/Renderer.hpp>
#include "private-access.hpp"
#include <hyprland/src/desktop/view/Window.hpp>
#include <hyprland/src/state/MonitorState.hpp>

namespace {
using namespace hics::capture;
HANDLE handle = nullptr;
CFunctionHook* commitHook = nullptr;
using Commit = void (*)(Screenshare::CScreenshareManager*, PHLMONITOR);
void onCommit(Screenshare::CScreenshareManager* manager, PHLMONITOR monitor) {
    reinterpret_cast<Commit>(commitHook->m_original)(manager, monitor);
    if (!monitor) return;
    // Native onOutputCommit already handled output/region exports and windows
    // intersecting the output. Only finish window frames its position guard
    // skipped. Frame::copy retains all native permission/no-screen-share checks.
    const auto pending = (manager->*member(Pending{}));
    for (const auto& weak : pending) {
        const auto frame = weak;
        if (!frame || !(frame.get()->*member(Shared{})) || frame->done() || (frame.get()->*member(Copying{}))) continue;
        const auto session = (frame.get()->*member(Session{}));
        if (!session || (session.get()->*member(Kind{})) != Screenshare::SHARE_WINDOW || session->monitor() != monitor) continue;
        const auto window = (session.get()->*member(Window{})).lock();
        if (!validMapped(window) || window->isHidden()) continue;
        const auto geometry = window->geometricBox(Desktop::View::IGeometric::GEOMETRIC_CURRENT);
        if (!geometry.intersection(monitor->logicalBox()).empty()) continue;
        (frame.get()->*member(Copy{}))();
    }
    std::erase_if((manager->*member(Pending{})), [](const auto& frame) { return !frame || frame->done(); });
}
}
APICALL EXPORT std::string PLUGIN_API_VERSION() { return HYPRLAND_API_VERSION; }
APICALL EXPORT PLUGIN_DESCRIPTION_INFO PLUGIN_INIT(HANDLE pluginHandle) {
    handle = pluginHandle;
    if (std::string(__hyprland_api_get_hash()) != __hyprland_api_get_client_hash())
        throw std::runtime_error("hics capture: compositor ABI mismatch");
    for (const auto& function : HyprlandAPI::findFunctionsByName(handle, "onOutputCommit")) {
        if (function.demangled.find("Screenshare::CScreenshareManager::onOutputCommit(") == std::string::npos) continue;
        commitHook = HyprlandAPI::createFunctionHook(handle, function.address, reinterpret_cast<void*>(onCommit));
        if (!commitHook || !commitHook->hook()) throw std::runtime_error("hics capture: cannot attach export adapter");
        for (const auto& monitor : State::monitorState()->monitors())
            if (monitor) g_pHyprRenderer->damageMonitor(monitor);
        return {"hics-capture", "Window export for canvas coordinates", "hics", "1.0"};
    }
    throw std::runtime_error("hics capture: screenshare commit function not found");
}
APICALL EXPORT void PLUGIN_EXIT() {
    if (commitHook) commitHook->unhook();
    commitHook = nullptr;
}
