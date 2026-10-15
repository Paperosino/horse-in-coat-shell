// Hyprstack visual task animation for the pinned Hyprland 0.56 renderer.
// The client's layout and configured size stay intact throughout the animation.
#pragma once

#include <hyprland/src/desktop/view/Window.hpp>
#include <hyprland/src/desktop/state/WindowState.hpp>
#include <hyprland/src/managers/eventLoop/EventLoopManager.hpp>
#include <hyprland/src/render/Renderer.hpp>
#include <hyprland/src/render/pass/ClearPassElement.hpp>
#include <hyprland/src/render/transformer/Transformer.hpp>
#include <hyprutils/utils/ScopeGuard.hpp>
#include <algorithm>
#include <chrono>

class CTaskAnimation final : public Render::IWindowTransformer {
  public:
    CTaskAnimation(PHLWINDOW window, const CBox& from, const CBox& to, double panelTop) :
        m_window(window), m_from(from), m_to(to), m_panelTop(panelTop) {
        // The entire swept area is safe even when rendering is delayed. Leave
        // the rest of the output (and other outputs) outside the damage region.
        const double left = std::min(from.x, to.x), top = std::min(from.y, to.y);
        m_damage = CBox{left, top, std::max(from.x + from.w, to.x + to.w) - left,
            std::max(from.y + from.h, to.y + to.h) - top}.expand(2);
        m_timer = makeShared<CEventLoopTimer>(std::chrono::milliseconds(1), [this](SP<CEventLoopTimer> timer, void*) {
            const auto window = m_window.lock();
            if (!window || !window->m_isMapped) return;
            if (const auto monitor = window->m_monitor.lock())
                monitor->addDamage(m_damage.copy().translate(-monitor->m_position).scale(monitor->m_scale).round());
            // Match the output's frame interval, including high-refresh displays.
            if (busy()) {
                const auto monitor = window->m_monitor.lock();
                timer->updateTimeout(std::chrono::milliseconds(monitor ?
                    std::max(1, static_cast<int>(std::floor(1000.0 / monitor->m_refreshRate))) : 8));
            }
        }, nullptr);
        g_pEventLoopManager->addTimer(m_timer);
    }

    ~CTaskAnimation() override {
        if (m_timer && g_pEventLoopManager) g_pEventLoopManager->removeTimer(m_timer);
    }

    bool busy() const { return elapsed() < 0.23; }

    CBox current() const {
        const double t = std::clamp(elapsed() / 0.22, 0.0, 1.0);
        const double p = t * t * (3.0 - 2.0 * t);
        return {m_from.pos() + (m_to.pos() - m_from.pos()) * p,
            m_from.size() + (m_to.size() - m_from.size()) * p};
    }

    void preWindowRender(CSurfacePassElement::SRenderData*) override {
        // Snapshot/standalone passes skip amendTransformedRenderData. They must
        // never reuse coordinates left behind by an earlier desktop frame.
        m_hasSource = false;
    }

    void amendTransformedRenderData(const CBox& source, SMotionBlurData* data) override {
        const auto monitor = g_pHyprRenderer->m_renderData.pMonitor;
        if (!monitor || !data) return;
        m_source = source;
        m_destination = current().translate(-monitor->m_position);
        m_hasSource = true;
        // A single sample provides a bounded transformed pass, without blur or fading.
        data->enabled = true;
        data->previous = data->current = m_destination;
        data->samples = 1;
    }

    SP<Render::IFramebuffer> transform(SP<Render::IFramebuffer> in) override {
        const auto monitor = g_pHyprRenderer->m_renderData.pMonitor;
        if (!monitor || !m_hasSource || m_source.w < 1 || m_source.h < 1) return in;
        const auto output = monitor->resources()->getUnusedWorkBuffer();
        if (!output) return in;
        // The bounding pass, colour texture and blur matte share one timestamp.
        // Re-sampling time here clips moving edges and misaligns transparency.
        const Vector2D ratio = m_destination.size() / m_source.size();
        auto guard = g_pHyprRenderer->bindTempFB(output);
        auto& render = g_pHyprRenderer->m_renderData;
        const auto sourceDamage = render.damage.copy();
        Hyprutils::Utils::CScopeGuard damageGuard([&render, sourceDamage] { render.damage = sourceDamage; });
        // The nested window pass leaves damage in source coordinates. Clear
        // the full scratch buffer before drawing in destination coordinates,
        // otherwise its uninitialised pixels appear as noise around the shadow.
        render.damage = CRegion{0, 0, static_cast<int>(monitor->m_transformedSize.x), static_cast<int>(monitor->m_transformedSize.y)};
        g_pHyprRenderer->draw(CClearPassElement::SClearData{CHyprColor(0, 0, 0, 0)});
        CTexPassElement::SRenderData texture;
        texture.tex = in->getTexture();
        texture.box = {(m_destination.pos() - m_source.pos() * ratio) * monitor->m_scale, in->m_size * ratio};
        // The image enters its task button behind the bar instead of becoming
        // a point above it. This also works with a translucent taskbar.
        const double panelTop = (m_panelTop - monitor->m_position.y) * monitor->m_scale;
        if (panelTop > monitor->m_transformedSize.y / 2)
            texture.clipBox = {0, 0, monitor->m_transformedSize.x, std::max(1.0, panelTop)};
        else {
            const auto task = m_from.h < m_to.h ? m_from : m_to;
            const double bottom = (task.y + task.h - monitor->m_position.y + 4) * monitor->m_scale;
            texture.clipBox = {0, bottom, monitor->m_transformedSize.x, std::max(1.0, monitor->m_transformedSize.y - bottom)};
        }
        g_pHyprRenderer->draw(texture, CRegion{m_destination.copy().scale(monitor->m_scale).expand(2).round()});
        return output;
    }

    static CTaskAnimation* find(PHLWINDOW window) {
        for (const auto& transformer : window->m_transformers)
            if (auto task = dynamic_cast<CTaskAnimation*>(transformer.get())) return task;
        return nullptr;
    }

    static void clear(PHLWINDOW window) {
        if (!window) return;
        const auto task = find(window);
        if (!task) return;
        const auto damage = task->m_damage;
        std::erase_if(window->m_transformers, [](const auto& t) { return dynamic_cast<CTaskAnimation*>(t.get()) != nullptr; });
        if (const auto monitor = window->m_monitor.lock())
            monitor->addDamage(damage.copy().translate(-monitor->m_position).scale(monitor->m_scale).round());
    }

  private:
    double elapsed() const { return std::chrono::duration<double>(Time::steadyNow() - m_start).count(); }
    PHLWINDOWREF m_window;
    CBox m_from, m_to, m_source, m_destination, m_damage;
    bool m_hasSource = false;
    double m_panelTop;
    Time::steady_tp m_start = Time::steadyNow();
    SP<CEventLoopTimer> m_timer;
};
