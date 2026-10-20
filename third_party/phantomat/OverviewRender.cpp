#include "OverviewRender.hpp"
#include <chrono>
#include <cmath>
#include <sstream>
#include <hyprland/src/render/Renderer.hpp>
#include <hyprland/src/render/pass/RectPassElement.hpp>
#include <hyprutils/utils/ScopeGuard.hpp>

namespace OverviewRender {

void flushPass(PHLMONITOR monitor) {
    if (!monitor || g_pHyprRenderer->m_renderPass.empty())
        return;

    // Sub-passes include wallpaper capture into temporary framebuffers. Their
    // per-element damage and clipping must never become the next pass's state.
    auto& state = g_pHyprRenderer->m_renderData;
    const auto damage = state.damage;
    const auto clip = state.clipBox;
    const auto transform = state.renderModif;
    const auto window = state.currentWindow;
    const auto uvTL = state.primarySurfaceUVTopLeft, uvBR = state.primarySurfaceUVBottomRight;
    const auto nearest = state.useNearestNeighbor;
    Hyprutils::Utils::CScopeGuard restore([&] {
        state.damage = damage; state.clipBox = clip; state.renderModif = transform;
        state.currentWindow = window; state.primarySurfaceUVTopLeft = uvTL;
        state.primarySurfaceUVBottomRight = uvBR; state.useNearestNeighbor = nearest;
    });
    g_pHyprRenderer->m_renderPass.render(CRegion{CBox{{}, monitor->m_transformedSize}});
    g_pHyprRenderer->m_renderPass.clear();
}

void queueBlur(const CBox& box, int rounding, float roundingPower, float alpha, bool usePrecomputedBlur) {
    if (alpha <= 0.F)
        return;

    if (box.empty())
        return;

    CRectPassElement::SRectData data;
    data.box           = box;
    data.color         = CHyprColor{0.F, 0.F, 0.F, 0.F};
    data.round         = rounding;
    data.roundingPower = roundingPower;
    data.blur          = true;
    data.blurA         = alpha;
    data.xray          = usePrecomputedBlur;
    g_pHyprRenderer->m_renderPass.add(makeUnique<CRectPassElement>(data));
}

void renderBlur(PHLMONITOR monitor, const CBox& box, int rounding, float roundingPower, float alpha, bool usePrecomputedBlur) {
    if (!monitor)
        return;

    queueBlur(box, rounding, roundingPower, alpha, usePrecomputedBlur);
    flushPass(monitor);
}

}
