#pragma once
#include "gpumetricssampler.hpp"
#include "performancepolicy.hpp"
#include "prefetchpolicy.hpp"
#include <QElapsedTimer>
#include <QObject>
#include <QProcess>
#include <QTimer>
#include <QVariantMap>
#include <QtQmlIntegration/qqmlintegration.h>

namespace hyprstack::services {
class RuntimePerformance : public QObject {
  Q_OBJECT
  QML_ELEMENT
  QML_SINGLETON
  Q_PROPERTY(QVariantMap settings READ settings NOTIFY settingsChanged)
  Q_PROPERTY(QVariantMap status READ status NOTIFY statusChanged)
  Q_PROPERTY(bool autoGame READ autoGame NOTIFY gameChanged)
  Q_PROPERTY(int gamePid READ gamePid NOTIFY gameChanged)
  Q_PROPERTY(int quality READ quality NOTIFY statusChanged)
  Q_PROPERTY(bool thermalLimited READ thermalLimited NOTIFY statusChanged)
public:
  explicit RuntimePerformance(QObject *parent = nullptr);
  ~RuntimePerformance() override;
  QVariantMap settings() const { return m_settings; }
  QVariantMap status() const { return m_status; }
  bool autoGame() const { return m_autoGame; }
  int gamePid() const { return m_gamePid; }
  int quality() const { return m_policy.hot ? 0 : m_policy.level; }
  bool thermalLimited() const { return m_policy.hot; }
  Q_INVOKABLE bool set(const QString &key, const QVariant &value);
  Q_INVOKABLE void observeWindow(const QVariantMap &window,
                                 const QString &desktopId = {},
                                 const QString &executable = {});
  Q_INVOKABLE void setSessionState(bool gameMode, bool onBattery, bool locked);
  Q_INVOKABLE void forgetHistory();
signals:
  void settingsChanged();
  void statusChanged();
  void gameChanged();

private:
  void evaluateGame();
  void publishGameActivity();
  void updateTimer();
  void sample();
  void updateLease();
  void queueStatus();
  void failLease(QProcess *process, const char *reason);
  void saveHistory();
  void tryPrefetch();
  void stopPrefetch();
  QString m_directory, m_historyPath;
  QVariantMap m_settings, m_status, m_window;
  QString m_desktopId, m_executable;
  using Visit = hics::performance::Visit;
  QList<Visit> m_visits;
  QTimer m_timer, m_saveTimer;
  QElapsedTimer m_clock;
  hics::performance::QualityPolicy m_policy;
  quint64 m_lastIdle = 0, m_lastTotal = 0;
  bool m_loading = false;
  bool m_autoGame = false, m_gameMode = false, m_onBattery = false,
       m_locked = false;
  int m_gamePid = 0;
  qint64 m_lastPrefetch = -3600000, m_sampledAt = -3600000;
  QProcess *m_lease = nullptr;
  QString m_leaseKey;
  bool m_statusQueued = false;
  hics::performance::GpuMetricsSampler m_nvidia;
  double m_nvidiaUsage = -1, m_nvidiaTemperature = -1;
  qint64 m_nvidiaSampledAt = -3600000;
  QProcess *m_prefetch = nullptr;
  quint64 m_prefetchSerial = 0;
};
} // namespace hyprstack::services
