#include "tickingservice.hpp"
#include "telemetrypolicy.hpp"
#include <QEvent>

#include "config/dashboardconfig.hpp"
#include "config/rootnodes.hpp"

namespace hyprstack::services {
bool TickingService::gaming(){return hics::performance::telemetryGaming();}
void TickingService::setGameMode(bool active){hics::performance::setTelemetryGaming(active);}
bool TickingService::eventFilter(QObject* watched,QEvent* event){
 if(watched==hics::performance::telemetryPolicy()&&event->type()==QEvent::DynamicPropertyChange)applyInterval(m_baseInterval);
 return Service::eventFilter(watched,event);
}
TickingService::TickingService(QObject* parent)
    : Service(parent)
    , m_timer(new QTimer(this)) {
    hics::performance::telemetryPolicy()->installEventFilter(this);
    m_timer->setSingleShot(false);
    QObject::connect(m_timer, &QTimer::timeout, this, [this] {
        tick();
    });

    const auto* dash = hyprstack::config::ConfigSingleton::instance()->dashboard();
    applyInterval(dash->resourceUpdateInterval());
    QObject::connect(dash, &hyprstack::config::DashboardConfig::resourceUpdateIntervalChanged, this, [this, dash] {
        applyInterval(dash->resourceUpdateInterval());
    });
}

int TickingService::updateInterval() const {
    return m_interval;
}

void TickingService::start() {
    m_running = true;
    if (m_interval > 0) {
        m_timer->start(m_interval);
    }
    tick();
}

void TickingService::stop() {
    m_running = false;
    m_timer->stop();
    onStopped();
}

void TickingService::applyInterval(int ms) {
    m_baseInterval = qMax(250, ms);
    ms = m_baseInterval * (gaming() ? 5 : 1);
    if (ms == m_interval) {
        return;
    }
    m_interval = ms;
    if (m_running) {
        m_timer->start(m_interval);
    }
    emit updateIntervalChanged();
}

} // namespace hyprstack::services
