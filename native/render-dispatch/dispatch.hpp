#pragma once
#include <hyprland/src/plugins/PluginAPI.hpp>
#include <hyprland/src/render/pass/TexPassElement.hpp>
namespace hics::render {
using Draw = void (*)(void*, WP<CTexPassElement>, const CRegion&);
using Callback = void (*)(void*, WP<CTexPassElement>, const CRegion&, Draw);
// Main compositor thread only. Exactly one patch regardless of participants.
bool attach(HANDLE owner, Callback callback, int priority, bool enabled);
void enable(Callback callback, bool enabled);
void detach(HANDLE owner);
struct Diagnostics { unsigned patches, participants; int activePriority; };
Diagnostics diagnostics();
}
