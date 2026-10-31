// Render-only perspective and spring for an actively moved stacking window.
#pragma once
#include "drag-inertia.hpp"
#include "perspective.hpp"
#include <hyprland/src/layout/LayoutManager.hpp>
#include <hyprland/src/desktop/state/FocusState.hpp>
#include <hyprland/src/managers/eventLoop/EventLoopManager.hpp>
#include <hyprland/src/render/pass/ClearPassElement.hpp>
#include <hyprland/src/render/transformer/Transformer.hpp>

class CStackDragTilt final : public Render::IWindowTransformer {
  public:
    CStackDragTilt(PHLWINDOW window, Vector2D position, bool (*enabled)()) : m_window(window), m_enabled(enabled) {
        m_last = Time::steadyNow();
        m_physics.reset(position.x, position.y, seconds(m_last));
        m_timer = makeShared<CEventLoopTimer>(std::chrono::milliseconds(1), [this](SP<CEventLoopTimer> timer, void*) {
            const auto window = m_window.lock();
            if (!window || !window->m_isMapped) return;
            const auto now = Time::steadyNow();
            if (std::chrono::duration<double>(now-m_lastPolicy).count() >= .1) {
                m_lastPolicy = now;
                if (!m_enabled()) {
                    const PHLWINDOWREF weak=window; auto self=this;
                    m_cleanup=g_pEventLoopManager->doLater([weak,self]{if(auto w=weak.lock();w && find(w)==self)clear(w);});
                    return;
                }
            }
            const auto target = g_layoutManager->dragController()->target();
            const bool dragging = target && target->window() == window && g_layoutManager->dragController()->mode() == MBIND_MOVE;
            if (!dragging) m_physics.settle(std::chrono::duration<double>(now-m_last).count());
            m_last = now;
            if (auto monitor=window->m_monitor.lock()) {
                monitor->addDamage(window->getFullWindowBoundingBox().expand(160).translate(-monitor->m_position).scale(monitor->m_scale).round());
                timer->updateTimeout(std::chrono::milliseconds(std::max(1,static_cast<int>(1000.0/monitor->m_refreshRate))));
            }
            if (!dragging && m_physics.settled()) {
                const PHLWINDOWREF weak=window; auto self=this;
                m_cleanup=g_pEventLoopManager->doLater([weak,self]{if(auto w=weak.lock();w && find(w)==self)clear(w);});
            }
        },nullptr);
        g_pEventLoopManager->addTimer(m_timer);
    }
    ~CStackDragTilt() override {
        if(m_cleanup && g_pEventLoopManager)g_pEventLoopManager->removeDoLater(m_cleanup);
        if(m_timer && g_pEventLoopManager)g_pEventLoopManager->removeTimer(m_timer);
    }
    void move(Vector2D position) { m_physics.move(position.x,position.y,seconds(Time::steadyNow())); }
    double tiltX() const {return m_physics.tiltX();}
    double tiltY() const {return m_physics.tiltY();}
    int paints() const {return m_paints;}
    void preWindowRender(CSurfacePassElement::SRenderData*) override {m_hasSource=false;}
    void amendTransformedRenderData(const CBox& source, SMotionBlurData* data) override {
        if(!data)return;
        m_source=source;m_hasSource=true;
        data->enabled=false;data->previous=data->current=source;data->samples=1;
    }
    SP<Render::IFramebuffer> transform(SP<Render::IFramebuffer> input) override {
        const auto monitor=g_pHyprRenderer->m_renderData.pMonitor;
        if(!monitor || !m_hasSource || m_source.w<1 || m_source.h<1)return input;
        auto output=monitor->resources()->getUnusedWorkBuffer();
        if(!output)return input;
        if(!m_perspective.apply(input,output,m_source.copy().scale(monitor->m_scale),tiltX(),tiltY()))return input;
        ++m_paints;return output;
    }
    static CStackDragTilt* find(PHLWINDOW window) {
        for(const auto& t:window->m_transformers)if(auto p=dynamic_cast<CStackDragTilt*>(t.get()))return p;
        return nullptr;
    }
    static void clear(PHLWINDOW window) {
        if(!window)return;
        if(auto monitor=window->m_monitor.lock()) monitor->addDamage(window->getFullWindowBoundingBox().expand(160).translate(-monitor->m_position).scale(monitor->m_scale).round());
        std::erase_if(window->m_transformers,[](const auto& t){return dynamic_cast<CStackDragTilt*>(t.get())!=nullptr;});
    }
  private:
    static double seconds(const Time::steady_tp& t) {return std::chrono::duration<double>(t.time_since_epoch()).count();}
    PHLWINDOWREF m_window;
    hics::motion::DragInertia m_physics;
    hics::motion::Perspective m_perspective;
    CBox m_source;
    bool m_hasSource=false;
    int m_paints=0;
    uint64_t m_cleanup=0;
    bool (*m_enabled)();
    Time::steady_tp m_last, m_lastPolicy = Time::steadyNow();
    SP<CEventLoopTimer> m_timer;
};
