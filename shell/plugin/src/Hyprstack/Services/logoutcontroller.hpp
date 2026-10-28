#pragma once

#include <qobject.h>
#include <qqmlintegration.h>
#include <qtimer.h>
#include <qvariant.h>

namespace hyprstack::services {

class LogoutController : public QObject {
    Q_OBJECT
    QML_ELEMENT
    QML_SINGLETON
    Q_PROPERTY(bool active READ active NOTIFY changed)
    Q_PROPERTY(bool ready READ ready NOTIFY changed)
    Q_PROPERTY(bool busy READ busy NOTIFY changed)
    Q_PROPERTY(bool finishing READ finishing NOTIFY changed)
    Q_PROPERTY(bool locked READ locked WRITE setLocked NOTIFY changed)
    Q_PROPERTY(QVariantList blockers READ blockers NOTIFY changed)
    Q_PROPERTY(QString error READ error NOTIFY changed)
public:
    explicit LogoutController(QObject* parent = nullptr);
    ~LogoutController() override;
    bool active() const { return m_active; }
    bool ready() const { return m_ready; }
    bool busy() const { return m_busy; }
    bool finishing() const { return m_finishing; }
    bool locked() const { return m_locked; }
    QVariantList blockers() const { return m_blockers; }
    QString error() const { return m_error; }
    void setLocked(bool value);
    Q_INVOKABLE void request();
    Q_INVOKABLE void cancel();
    Q_INVOKABLE void commit();
    Q_INVOKABLE void force();
    Q_INVOKABLE void terminationFailed(const QString& reason);
signals:
    void changed();
    void exitApproved();
private:
    void startProbe(quint64 epoch);
    void checkProbe(quint64 epoch, int attempts);
    void closeProbe();
    void beginQuery(quint64 epoch);
    void refresh();
    void abortQuery();
    void reset();
    void setFailure(const QString& text);
    bool m_owned = false;
    bool m_locked = true;
    bool m_active = false;
    bool m_ready = false;
    bool m_busy = false;
    bool m_queryStarted = false;
    bool m_refreshing = false;
    bool m_finishing = false;
    quint64 m_epoch = 0;
    QVariantList m_blockers;
    QString m_error;
    QString m_probeReason;
    QString m_probePath;
    bool m_frontendLost = false;
    bool m_backendLost = false;
    QTimer m_timer;
};
}
