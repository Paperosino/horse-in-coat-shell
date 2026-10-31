// A render-only lift for overlapping stacking windows. Client geometry and
// input remain owned by Hyprland and never follow the temporary visual scale.
#pragma once
#include "task-animation.hpp"

class CStackFocusAnimation final : public Render::IWindowTransformer {
  public:
    CStackFocusAnimation(PHLWINDOW window, double stiffness, double damping, double amplitude, CHyprColor accent) :
        m_window(window), m_stiffness(stiffness), m_damping(damping), m_amplitude(amplitude), m_accent(accent) {
        m_damage = window->getFullWindowBoundingBox().expand(160);
        m_timer = makeShared<CEventLoopTimer>(std::chrono::milliseconds(1), [this](SP<CEventLoopTimer> timer, void*) {
            auto window = m_window.lock();
            if (!window || !window->m_isMapped) return;
            damage(window);
            if (elapsed() >= 0.8) {
                // Never destroy a transformer on its own timer callback stack.
                const PHLWINDOWREF weak = window;
                auto self = this;
                m_cleanup = g_pEventLoopManager->doLater([weak, self] {
                    if (auto w = weak.lock(); w && find(w) == self) clear(w);
                });
                return;
            }
            const auto monitor = window->m_monitor.lock();
            timer->updateTimeout(std::chrono::milliseconds(monitor ? std::max(1, static_cast<int>(1000.0 / monitor->m_refreshRate)) : 8));
        }, nullptr);
        g_pEventLoopManager->addTimer(m_timer);
    }
    ~CStackFocusAnimation() override {
        if (m_cleanup && g_pEventLoopManager) g_pEventLoopManager->removeDoLater(m_cleanup);
        if (m_timer && g_pEventLoopManager) g_pEventLoopManager->removeTimer(m_timer);
    }
    double scale() const {
        const double t = elapsed();
        if (t >= 0.8) return 1.0;
        const double omega = std::sqrt(m_stiffness);
        const double wd = omega * std::sqrt(1.0 - m_damping * m_damping);
        // Unit initial velocity impulse, normalized for comparable peak lifts.
        return 1.0 + m_amplitude * std::exp(-m_damping * omega * t) * std::sin(wd * t);
    }
    void preWindowRender(CSurfacePassElement::SRenderData*) override { m_hasSource = false; }
    void amendTransformedRenderData(const CBox& source, SMotionBlurData* data) override {
        const auto monitor = g_pHyprRenderer->m_renderData.pMonitor;
        if (!monitor || !data) return;
        m_source = source;
        const auto factor = scale();
        m_destination = {source.middle() - source.size() * factor * 0.5, source.size() * factor};
        m_hasSource = true;
        data->enabled = false;
        data->previous = data->current = m_destination;
        data->samples = 1;
    }
    SP<Render::IFramebuffer> transform(SP<Render::IFramebuffer> in) override {
        const auto monitor = g_pHyprRenderer->m_renderData.pMonitor;
        if (!monitor || !m_hasSource || m_source.w < 1 || m_source.h < 1) return in;
        const auto output = monitor->resources()->getUnusedWorkBuffer();
        if (!output) return in;
        const Vector2D ratio = m_destination.size() / m_source.size();
        auto guard = g_pHyprRenderer->bindTempFB(output);
        auto& render = g_pHyprRenderer->m_renderData;
        const auto sourceDamage = render.damage.copy();
        Hyprutils::Utils::CScopeGuard damageGuard([&render, sourceDamage] { render.damage = sourceDamage; });
        render.damage = CRegion{0, 0, monitor->m_transformedSize.x, monitor->m_transformedSize.y};
        g_pHyprRenderer->draw(CClearPassElement::SClearData{CHyprColor(0, 0, 0, 0)});
        // Before the handoff the outgoing window is composed once in the
        // overlay pass. Suppressing its normal pass avoids doubling alpha and
        // shadows for translucent clients outside the overlap.
        if (m_amplitude < 0 && elapsed() < peakTime()) {
            ++m_paints;
            return output;
        }
        // Soft, bounded shadow and a low-opacity tonal halo follow elevation.
        // Draw in the same offscreen pass as the client so they share the same
        // timestamp, damage and compositor colour management.
        if (m_amplitude > 0) {
            const double elevation = std::clamp((scale() - 1.0) / .025, 0.0, 1.0);
            const CBox box = m_destination.copy().scale(monitor->m_scale);
            for (int layer = 10; layer >= 1; --layer) {
                CRectPassElement::SRectData shadow;
                const double spread = layer * (1.0 + 2.0 * elevation) * monitor->m_scale;
                shadow.box = box.copy().expand(spread).translate({0.0, (2.0 + elevation * 7.0) * monitor->m_scale});
                shadow.round = std::lround(12.0 * monitor->m_scale + spread);
                shadow.color = CHyprColor(0, 0, 0, (.006 + elevation * .008) * (11 - layer));
                g_pHyprRenderer->draw(shadow, render.damage);
            }
            if (elevation > .01) {
                CRectPassElement::SRectData halo;
                halo.box = box.copy().expand(5 * monitor->m_scale);
                halo.round = std::lround(18 * monitor->m_scale);
                halo.color = m_accent.modifyA(.045 * elevation);
                g_pHyprRenderer->draw(halo, render.damage);
            }
        }
        CTexPassElement::SRenderData texture;
        texture.tex = in->getTexture();
        texture.box = {(m_destination.pos() - m_source.pos() * ratio) * monitor->m_scale, in->m_size * ratio};
        g_pHyprRenderer->draw(texture, CRegion{m_destination.copy().scale(monitor->m_scale).expand(2).round()});
        ++m_paints;
        return output;
    }
    int paints() const { return m_paints; }
    double progress() const { return elapsed(); }
    double peakTime() const {
        const double omega = std::sqrt(m_stiffness);
        const double wd = omega * std::sqrt(1.0 - m_damping * m_damping);
        return std::atan2(wd, m_damping * omega) / wd;
    }
    static CStackFocusAnimation* find(PHLWINDOW window) {
        for (const auto& t : window->m_transformers)
            if (auto focus = dynamic_cast<CStackFocusAnimation*>(t.get())) return focus;
        return nullptr;
    }
    static void clear(PHLWINDOW window) {
        if (!window) return;
        auto animation = find(window);
        if (!animation) return;
        animation->damage(window);
        std::erase_if(window->m_transformers, [](const auto& t) { return dynamic_cast<CStackFocusAnimation*>(t.get()) != nullptr; });
    }
  private:
    void damage(PHLWINDOW window) const {
        if (const auto monitor = window->m_monitor.lock())
            monitor->addDamage(m_damage.copy().translate(-monitor->m_position).scale(monitor->m_scale).round());
    }
    double elapsed() const { return std::chrono::duration<double>(Time::steadyNow() - m_start).count(); }
    PHLWINDOWREF m_window;
    CBox m_source, m_destination, m_damage;
    bool m_hasSource = false;
    double m_stiffness, m_damping, m_amplitude;
    CHyprColor m_accent;
    int m_paints = 0;
    uint64_t m_cleanup = 0;
    Time::steady_tp m_start = Time::steadyNow();
    SP<CEventLoopTimer> m_timer;
};
