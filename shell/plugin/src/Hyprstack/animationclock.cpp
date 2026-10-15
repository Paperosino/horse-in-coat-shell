#include "animationclock.hpp"

#include <qguiapplication.h>
#include <qscreen.h>
#include <qqmlengine.h>
#include <private/qsgrenderloop_p.h>

#include <algorithm>
#include <chrono>
#include <cmath>

namespace hyprstack {

AnimationClock* AnimationClock::create(QQmlEngine*, QJSEngine*) {
    // Quickshell loads the new engine before destroying the old one during a
    // reload. Share one process-wide clock across those overlapping engines.
    static QPointer<AnimationClock> instance;
    if (!instance) instance = new AnimationClock(qGuiApp);
    QQmlEngine::setObjectOwnership(instance, QQmlEngine::CppOwnership);
    return instance;
}

AnimationClock::AnimationClock(QObject* parent) : QAnimationDriver(parent) {
    m_tick.setTimerType(Qt::PreciseTimer);
    connect(&m_tick, &QChronoTimer::timeout, this, &AnimationClock::advance);
    connect(this, &QAnimationDriver::started, this, &AnimationClock::runningChanged);
    connect(this, &QAnimationDriver::stopped, this, &AnimationClock::runningChanged);
    connect(qGuiApp, &QGuiApplication::screenAdded, this, [this] { watchScreens(); updateRate(); });
    connect(qGuiApp, &QGuiApplication::screenRemoved, this, [this] { watchScreens(); updateRate(); });
    watchScreens();
    updateRate();
}

AnimationClock::~AnimationClock() {
    m_tick.stop();
    if (m_installed) {
        uninstall();
        // Restore Qt's driver if the clock is explicitly destroyed while the
        // process-wide render loop is still alive.
        if (m_previous) m_previous->install();
    }
}

void AnimationClock::activate() {
    if (m_installed) return;
    // The render loop must exist before replacing its main-thread driver.
    // Render-thread Animator clocks remain owned by their respective windows.
    m_previous = QSGRenderLoop::instance()->animationDriver();
    if (m_previous) m_previous->uninstall();
    install();
    m_installed = true;
}

void AnimationClock::watchScreens() {
    for (auto* screen : qGuiApp->screens())
        connect(screen, &QScreen::refreshRateChanged, this, &AnimationClock::updateRate, Qt::UniqueConnection);
}

void AnimationClock::updateRate() {
    qreal rate = 0;
    for (const auto* screen : qGuiApp->screens())
        if (std::isfinite(screen->refreshRate())) rate = std::max(rate, screen->refreshRate());
    rate = std::clamp(rate > 0 ? rate : 60.0, 30.0, 500.0);
    m_tick.setInterval(std::chrono::nanoseconds(std::llround(1'000'000'000.0 / rate)));
    if (!qFuzzyCompare(rate, m_refreshRate)) {
        m_refreshRate = rate;
        emit refreshRateChanged();
    }
}

qint64 AnimationClock::elapsed() const {
    return m_elapsed.isValid() ? m_elapsed.elapsed() : 0;
}

void AnimationClock::start() {
    m_elapsed.start();
    QAnimationDriver::start();
    m_tick.start();
}

void AnimationClock::stop() {
    m_tick.stop();
    QAnimationDriver::stop();
}

} // namespace hyprstack
