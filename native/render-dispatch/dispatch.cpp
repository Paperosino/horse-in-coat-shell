#include "dispatch.hpp"
#include <algorithm>
#include <vector>
#include <cstdio>
namespace hics::render {
namespace {
struct Client { HANDLE owner; Callback callback; int priority; bool enabled; };
std::vector<Client> clients;
CFunctionHook* hook = nullptr;
HANDLE hookOwner = nullptr;
unsigned patches = 0;
// Cache a value, never an address into the mutable registration vector.
Callback selectedCallback = nullptr;
int selectedPriority = -1;
void selectClient() {
    selectedCallback = nullptr; selectedPriority = -1;
    for (const auto& client : clients)
        if (client.enabled && (!selectedCallback || client.priority > selectedPriority)) {
            selectedCallback = client.callback; selectedPriority = client.priority;
        }
}
void dispatch(void* renderer, WP<CTexPassElement> element, const CRegion& damage) {
    const auto original = reinterpret_cast<Draw>(hook->m_original);
    if (selectedCallback) selectedCallback(renderer, element, damage, original);
    else original(renderer, element, damage);
}
bool install(HANDLE owner) {
    for (const auto& symbol : HyprlandAPI::findFunctionsByName(owner, "drawTex")) {
        if (!symbol.demangled.starts_with("Render::IElementRenderer::drawTex(")) continue;
        hook = HyprlandAPI::createFunctionHook(owner, symbol.address, reinterpret_cast<void*>(dispatch));
        if (hook && hook->hook()) { hookOwner = owner; ++patches; return true; }
        if (hook) HyprlandAPI::removeFunctionHook(owner, hook);
        hook = nullptr;
        return false;
    }
    return false;
}
}
bool attach(HANDLE owner, Callback callback, int priority, bool enabled) {
    for (const auto& client : clients) if (client.callback == callback) return true;
    if (!hook && !install(owner)) return false;
    clients.push_back({owner, callback, priority, enabled});
    selectClient();
    return true;
}
void enable(Callback callback, bool enabled) {
    for (auto& client : clients) if (client.callback == callback) client.enabled = enabled;
    selectClient();
}
Diagnostics diagnostics() {
    return {patches, static_cast<unsigned>(clients.size()), selectedPriority};
}
void detach(HANDLE owner) {
    std::erase_if(clients, [owner](const auto& client) { return client.owner == owner; });
    selectClient();
    if (hookOwner != owner) return;
    // Only plugin teardown transfers ownership. Remove the sole patch before
    // attaching a new one, so a trampoline can never target another trampoline.
    HyprlandAPI::removeFunctionHook(owner, hook);
    hook = nullptr; hookOwner = nullptr;
    if (!clients.empty() && !install(clients.front().owner))
        std::fputs("hics: texture dispatcher disabled after ownership transfer failure\n", stderr);
}
}
