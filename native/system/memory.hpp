#pragma once
#include "backend.hpp"
namespace Memory {
inline constexpr auto ConfigPath = "/etc/hics/memory.json";
inline constexpr auto RuntimePath = "/run/hics-memory/status.json";
inline constexpr auto SwapDirectory = "/var/lib/hics-memory/swap";
QJsonObject defaults();
QJsonObject configuration();
QJsonObject validate(const QJsonObject &options);
QJsonObject metrics();
// Stages only advance under pressure. Returning to idle is a separate,
// headroom-checked operation; a low sample never forces pages into RAM.
bool recoveryPressureLow(const QJsonObject &config, double total,
                         double available, double swapped);
int targetStage(const QJsonObject &config, int stage, double ramPercent,
                double zramPercent);
} // namespace Memory
namespace System {
QJsonObject memoryStatus();
void memoryApply(const QJsonObject &options);
} // namespace System
