#pragma once

#include <qqmlintegration.h>

#include "tickingservice.hpp"

namespace hyprstack::services {

class Cpu : public TickingService {
    Q_OBJECT
    QML_ELEMENT
    QML_SINGLETON

    Q_PROPERTY(QString name READ name NOTIFY nameChanged)
    Q_PROPERTY(qreal percentage READ percentage NOTIFY percentageChanged)
    Q_PROPERTY(qreal temperature READ temperature NOTIFY temperatureChanged)
    Q_PROPERTY(bool temperatureAvailable READ temperatureAvailable NOTIFY temperatureChanged)

public:
    explicit Cpu(QObject* parent = nullptr);

    [[nodiscard]] QString name() const;
    [[nodiscard]] qreal percentage() const;
    [[nodiscard]] qreal temperature() const;
    [[nodiscard]] bool temperatureAvailable() const;

signals:
    void nameChanged();
    void percentageChanged();
    void temperatureChanged();

protected:
    void tick() override;

private:
    void readNameOnce();
    void refreshPercentage();
    void refreshTemperature();

    [[nodiscard]] static QString cleanName(QString s);

    QString m_name;
    qreal m_percentage = 0.0;
    qreal m_temperature = 0.0;
    bool m_temperatureAvailable = false;
    quint64 m_lastIdle = 0;
    quint64 m_lastTotal = 0;
    bool m_nameLoaded = false;
};

} // namespace hyprstack::services
