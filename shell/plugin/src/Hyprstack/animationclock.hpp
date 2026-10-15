#pragma once

#include <qabstractanimation.h>
#include <qchronotimer.h>
#include <qelapsedtimer.h>
#include <qpointer.h>
#include <qqmlintegration.h>

class QQmlEngine;
class QJSEngine;

namespace hyprstack {

// A single main-thread clock for all outputs. Qt's elapsed-time scenegraph
// driver advances once per window sync, so multiple outputs can advance it
// repeatedly within a millisecond and repaint each other's idle windows.
// Its vsync-based alternative falls back to the primary output's rate instead.
class AnimationClock : public QAnimationDriver {
    Q_OBJECT
    QML_ELEMENT
    QML_SINGLETON

    Q_PROPERTY(bool running READ isRunning NOTIFY runningChanged)
    Q_PROPERTY(qreal refreshRate READ refreshRate NOTIFY refreshRateChanged)

public:
    // A required parent makes QML use create(), rather than constructing a
    // separate driver for each engine during Quickshell's overlapping reload.
    explicit AnimationClock(QObject* parent);
    ~AnimationClock() override;
    static AnimationClock* create(QQmlEngine*, QJSEngine*);
    Q_INVOKABLE void activate();
    qint64 elapsed() const override;
    qreal refreshRate() const { return m_refreshRate; }

signals:
    void runningChanged();
    void refreshRateChanged();

protected:
    void start() override;
    void stop() override;

private:
    void updateRate();
    void watchScreens();

    QChronoTimer m_tick;
    QElapsedTimer m_elapsed;
    QPointer<QAnimationDriver> m_previous;
    qreal m_refreshRate = 60;
    bool m_installed = false;
};

} // namespace hyprstack
