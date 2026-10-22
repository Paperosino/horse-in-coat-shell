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
#include <cmath>
#include <hyprland/src/render/pass/RectPassElement.hpp>
#include <hyprgraphics/image/Image.hpp>

class CExpressiveTaskAnimation final : public Render::IWindowTransformer {
  public:
    CExpressiveTaskAnimation(PHLWINDOW window, const CBox& from, const CBox& to, double duration, double damping, std::string icon, CHyprColor surface, CHyprColor accent) :
        m_window(window), m_from(from), m_to(to), m_duration(duration), m_damping(damping), m_iconPath(std::move(icon)), m_surface(surface), m_accent(accent), m_minimizing(to.w * to.h < from.w * from.h) {
        // The entire swept area is safe even when rendering is delayed. Leave
        // the rest of the output (and other outputs) outside the damage region.
        const double left = std::min(from.x, to.x), top = std::min(from.y, to.y);
        m_damage = CBox{left, top, std::max(from.x + from.w, to.x + to.w) - left,
            std::max(from.y + from.h, to.y + to.h) - top}.expand(48);
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

    ~CExpressiveTaskAnimation() override {
        if (m_timer && g_pEventLoopManager) g_pEventLoopManager->removeTimer(m_timer);
    }

    int renderCount() const { return m_renderCount; }
    int paintCount() const { return m_paintCount; }
    bool busy() const { return elapsed() < m_duration; }
    double progress() const { return std::clamp(elapsed() / m_duration, 0.0, 1.0); }
    double spring(double t) const {
        // Analytic damped spring, evaluated once per output frame. Normalize
        // the endpoint so finishing cannot produce a final position snap.
        const double z = std::clamp(m_damping, 0.55, 0.99), omega = 11.0;
        const double wd = omega * std::sqrt(1.0 - z * z);
        const auto response = [=](double x) { return 1.0 - std::exp(-z * omega * x) *
            (std::cos(wd * x) + z * omega / wd * std::sin(wd * x)); };
        return response(t) / response(1.0);
    }
    CBox current() const {
        const double t = progress(), p = spring(t);
        const double shape = std::clamp(spring(std::min(1.0, t * (m_minimizing ? 1.3 : 1.0))), 0.0, 1.0);
        auto size = m_from.size() + (m_to.size() - m_from.size()) * shape;
        const auto direction = m_to.middle() - m_from.middle();
        const double stretch = std::sin(t * M_PI) * 0.12;
        if (std::abs(direction.y) > std::abs(direction.x)) { size.x *= 1.0 - stretch; size.y *= 1.0 + stretch; }
        else { size.x *= 1.0 + stretch; size.y *= 1.0 - stretch; }
        return {m_from.middle() + direction * p - size * 0.5, size};
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
        // The output is already composed in monitor coordinates. Keep its final
        // copy untransformed: the motion-blur shader samples a cropped source
        // and would apply the destination mapping a second time. Swept damage
        // bounds the work while the token handles shape and content fading.
        data->enabled = false;
        data->previous = data->current = m_destination;
        data->samples = 1;
    }

    SP<Render::IFramebuffer> transform(SP<Render::IFramebuffer> in) override {
        ++m_renderCount;
        const auto monitor = g_pHyprRenderer->m_renderData.pMonitor;
        if (!monitor || !m_hasSource || m_source.w < 1 || m_source.h < 1) return in;
        ++m_paintCount;
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
        render.damage = CRegion{0, 0, monitor->m_transformedSize.x, monitor->m_transformedSize.y};
        g_pHyprRenderer->draw(CClearPassElement::SClearData{CHyprColor(0, 0, 0, 0)});
        CTexPassElement::SRenderData texture;
        texture.tex = in->getTexture();
        texture.box = {(m_destination.pos() - m_source.pos() * ratio) * monitor->m_scale, in->m_size * ratio};
        const double t = progress();
        const double morph = m_minimizing ? t : 1.0 - t;
        const double contentAlpha = m_minimizing ? std::clamp(1.0 - elapsed() / 0.07, 0.0, 1.0)
            : std::clamp((elapsed() - (m_duration - 0.07)) / 0.07, 0.0, 1.0);
        const auto box = m_destination.copy().scale(monitor->m_scale);
        const double radius = std::min(box.w, box.h) * 0.5;
        const int rounding = static_cast<int>(std::lerp(24.0 * monitor->m_scale, radius, std::clamp(morph * 2.0, 0.0, 1.0)));
        const double fade = m_minimizing ? std::clamp((1.0 - t) / 0.12, 0.0, 1.0) : 1.0;
        // Rounded GPU surfaces replace unreadably squeezed window contents.
        // The compositor still owns the real client and its original geometry.
        for (int layer = 3; layer > 0; --layer) {
            CRectPassElement::SRectData shadow;
            shadow.box = box.copy().expand(layer * 5.0 * monitor->m_scale);
            shadow.round = rounding + layer * 5 * monitor->m_scale;
            shadow.color = m_accent.modifyA(0.025 * (1.0 - contentAlpha) * fade);
            g_pHyprRenderer->draw(shadow, render.damage);
        }
        CRectPassElement::SRectData token;
        token.box = box; token.round = rounding;
        token.color = m_surface.modifyA((1.0 - contentAlpha) * fade);
        g_pHyprRenderer->draw(token, render.damage);
        texture.a = contentAlpha;
        texture.round = rounding;
        texture.clipBox = box;
        g_pHyprRenderer->draw(texture, CRegion{box.copy().expand(2).round()});
        if (!m_iconAttempted) {
            m_iconAttempted = true;
            if (!m_iconPath.empty()) {
                Hyprgraphics::CImage image(m_iconPath, {96, 96});
                if (image.success()) m_icon = g_pHyprRenderer->createTexture(image.cairoSurface()->cairo());
            }
            if (!m_icon) {
                auto surface = cairo_image_surface_create(CAIRO_FORMAT_ARGB32,64,64);
                auto painter = cairo_create(surface);
                cairo_set_source_rgba(painter,m_accent.r,m_accent.g,m_accent.b,1);
                for (int row=0;row<3;row++) for (int column=0;column<3;column++) {
                    cairo_arc(painter,16+column*16,16+row*16,4,0,2*M_PI);cairo_fill(painter);
                }
                cairo_surface_flush(surface);
                m_icon = g_pHyprRenderer->createTexture(surface);
                cairo_destroy(painter);cairo_surface_destroy(surface);
            }
            m_icon->m_imageDescription = NColorManagement::getDefaultImageDescription();
        }
        if (m_icon && contentAlpha < 1.0) {
            CTexPassElement::SRenderData icon;
            const double size = std::min({box.w * 0.62, box.h * 0.62, 96.0 * monitor->m_scale});
            icon.tex = m_icon;
            icon.box = {box.middle() - Vector2D{size, size} * 0.5, {size, size}};
            icon.a = (1.0 - contentAlpha) * fade;
            g_pHyprRenderer->draw(icon, render.damage);
        }
        return output;
    }

    static CExpressiveTaskAnimation* find(PHLWINDOW window) {
        for (const auto& transformer : window->m_transformers)
            if (auto task = dynamic_cast<CExpressiveTaskAnimation*>(transformer.get())) return task;
        return nullptr;
    }

    static void clear(PHLWINDOW window) {
        if (!window) return;
        const auto task = find(window);
        if (!task) return;
        const auto damage = task->m_damage;
        std::erase_if(window->m_transformers, [](const auto& t) { return dynamic_cast<CExpressiveTaskAnimation*>(t.get()) != nullptr; });
        if (const auto monitor = window->m_monitor.lock())
            monitor->addDamage(damage.copy().translate(-monitor->m_position).scale(monitor->m_scale).round());
    }

  private:
    double elapsed() const { return std::chrono::duration<double>(Time::steadyNow() - m_start).count(); }
    PHLWINDOWREF m_window;
    CBox m_from, m_to, m_source, m_destination, m_damage;
    bool m_hasSource = false;
    int m_renderCount=0,m_paintCount=0;
    double m_duration, m_damping;
    std::string m_iconPath;
    CHyprColor m_surface, m_accent;
    bool m_minimizing, m_iconAttempted = false;
    SP<Render::ITexture> m_icon;
    Time::steady_tp m_start = Time::steadyNow();
    SP<CEventLoopTimer> m_timer;
};
