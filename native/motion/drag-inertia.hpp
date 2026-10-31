// Bounded, refresh-rate-independent velocity tracking for stacking drags.
// Coordinates are logical pixels; the integrator never changes client geometry.
#pragma once
#include <algorithm>
#include <cmath>

namespace hics::motion {
class DragInertia {
  public:
    void reset(double x, double y, double time) {
        m_x = x; m_y = y; m_last = time; m_velocityX = m_velocityY = 0;
        m_angleX = m_angleY = m_speedX = m_speedY = 0; m_initialized = true;
    }
    void move(double x, double y, double time) {
        if (!m_initialized) { reset(x, y, time); return; }
        const double dt = time - m_last;
        if (dt <= 0) return;
        // Ignore stale events rather than treating a cursor jump after an idle
        // period as sustained velocity. Clamp before filtering to reject spikes.
        if (dt > .25) { reset(x, y, time); return; }
        const double blend = 1 - std::exp(-dt / .045);
        m_velocityX += (std::clamp((x - m_x) / dt, -2400.0, 2400.0) - m_velocityX) * blend;
        m_velocityY += (std::clamp((y - m_y) / dt, -2400.0, 2400.0) - m_velocityY) * blend;
        advance(dt, std::clamp(-m_velocityY / 2400.0, -.07, .07), std::clamp(m_velocityX / 2400.0, -.07, .07));
        m_x = x; m_y = y; m_last = time;
    }
    void settle(double dt) {
        if (!m_initialized || dt <= 0) return;
        advance(std::min(dt, .1), 0, 0);
    }
    double tiltX() const { return m_angleX; }
    double tiltY() const { return m_angleY; }
    bool settled() const { return std::abs(m_angleX) < .0001 && std::abs(m_angleY) < .0001 && std::abs(m_speedX) < .001 && std::abs(m_speedY) < .001; }
  private:
    static void axis(double& x, double& velocity, double target, double dt) {
        // Exact critically damped spring solution, stable even at low refresh.
        constexpr double omega = 15;
        const double displacement = x - target, c = velocity + omega * displacement, decay = std::exp(-omega * dt);
        x = target + (displacement + c * dt) * decay;
        velocity = (velocity - omega * c * dt) * decay;
    }
    void advance(double dt, double x, double y) { axis(m_angleX, m_speedX, x, dt); axis(m_angleY, m_speedY, y, dt); }
    bool m_initialized = false;
    double m_x = 0, m_y = 0, m_last = 0, m_velocityX = 0, m_velocityY = 0;
    double m_angleX = 0, m_angleY = 0, m_speedX = 0, m_speedY = 0;
};
}
