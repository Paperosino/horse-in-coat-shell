#pragma once

#include <qtimer.h>

#include "service.hpp"

namespace hyprstack::services {

class TickingService : public Service {
    Q_OBJECT

    Q_PROPERTY(int updateInterval READ updateInterval NOTIFY updateIntervalChanged)

public:
    explicit TickingService(QObject* parent = nullptr);
    static void setGameMode(bool active);
    static bool gaming();

    [[nodiscard]] int updateInterval() const;

signals:
    void updateIntervalChanged();

protected:
    bool eventFilter(QObject* watched,QEvent* event) override;
    virtual void tick() = 0;
    virtual void onStopped() {}

private:
    void start() final;
    void stop() final;

    void applyInterval(int ms);

    QTimer* m_timer;
    int m_interval = 1000, m_baseInterval = 1000;
    bool m_running = false;
};

} // namespace hyprstack::services
