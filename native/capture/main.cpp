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
// Like the other pinned native adapters, use the compositor's real declarations
// rather than offsets into private structures. ABI is checked at plugin load.
#define private public
#include <hyprland/src/managers/screenshare/ScreenshareManager.hpp>
#undef private
#include <hyprland/src/desktop/view/Window.hpp>
#include <hyprland/src/state/MonitorState.hpp>

namespace {
HANDLE handle = nullptr;
CFunctionHook* commitHook = nullptr;
using Commit = void (*)(Screenshare::CScreenshareManager*, PHLMONITOR);
void onCommit(Screenshare::CScreenshareManager* manager, PHLMONITOR monitor) {
    reinterpret_cast<Commit>(commitHook->m_original)(manager, monitor);
    if (!monitor) return;
    // Native onOutputCommit already handled output/region exports and windows
    // intersecting the output. Only finish window frames its position guard
    // skipped. Frame::copy retains all native permission/no-screen-share checks.
    const auto pending = manager->m_pendingFrames;
    for (const auto& weak : pending) {
        const auto frame = weak;
        if (!frame || !frame->m_shared || frame->done() || frame->m_copyInFlight) continue;
        const auto session = frame->m_session;
        if (!session || session->m_type != Screenshare::SHARE_WINDOW || session->monitor() != monitor) continue;
        const auto window = session->m_window.lock();
        if (!validMapped(window) || window->isHidden()) continue;
        const auto geometry = window->geometricBox(Desktop::View::IGeometric::GEOMETRIC_CURRENT);
        if (!geometry.intersection(monitor->logicalBox()).empty()) continue;
        frame->copy();
    }
    std::erase_if(manager->m_pendingFrames, [](const auto& frame) { return !frame || frame->done(); });
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
