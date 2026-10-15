#pragma once

#include <qqmlintegration.h>
#include <qvector.h>
#include "service.hpp"

namespace hyprstack::services {

// Keep the QML API available in builds without optional audio analysis.
// Volume, devices and media controls use Quickshell's PipeWire integration.
class CavaProvider : public Service {
    Q_OBJECT
    QML_ELEMENT
    Q_PROPERTY(int bars READ bars WRITE setBars NOTIFY barsChanged)
    Q_PROPERTY(QVector<double> values READ values NOTIFY valuesChanged)
    Q_PROPERTY(bool available READ available CONSTANT)
public:
    explicit CavaProvider(QObject* parent = nullptr) : Service(parent) {}
    [[nodiscard]] bool available() const { return false; }
    [[nodiscard]] int bars() const { return m_bars; }
    [[nodiscard]] QVector<double> values() const { return QVector<double>(m_bars, 0.0); }
    void setBars(int bars) {
        bars = qBound(0, bars, 256);
        if (m_bars == bars) return;
        m_bars = bars;
        emit barsChanged();
        emit valuesChanged();
    }
signals:
    void barsChanged();
    void valuesChanged();
private:
    int m_bars = 0;
    void start() override {}
    void stop() override {}
};

class BeatTracker : public Service {
    Q_OBJECT
    QML_ELEMENT
    Q_PROPERTY(float bpm READ bpm NOTIFY bpmChanged)
public:
    explicit BeatTracker(QObject* parent = nullptr) : Service(parent) {}
    [[nodiscard]] float bpm() const { return 120.0F; }
signals:
    void bpmChanged();
    void beat(float bpm);
private:
    void start() override {}
    void stop() override {}
};

} // namespace hyprstack::services
