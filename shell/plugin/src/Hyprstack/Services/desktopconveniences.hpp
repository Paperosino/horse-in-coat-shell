#pragma once
#include <QAudioSink>
#include <QBuffer>
#include <QDBusUnixFileDescriptor>
#include <QObject>
#include <QProcess>
#include <QVariantMap>
#include <QtQmlIntegration/qqmlintegration.h>
namespace hyprstack::services {
class DesktopConveniences : public QObject {
  Q_OBJECT
  QML_ELEMENT
  QML_SINGLETON
  Q_PROPERTY(bool dockInhibitRequested READ dockInhibitRequested WRITE
                 setDockInhibitRequested NOTIFY changed)
  Q_PROPERTY(bool dockInhibited READ dockInhibited NOTIFY changed)
  Q_PROPERTY(bool speakerTesting READ speakerTesting NOTIFY changed)
  Q_PROPERTY(bool cameraBlocked READ cameraBlocked NOTIFY changed)
  Q_PROPERTY(bool busy READ busy NOTIFY changed)
  Q_PROPERTY(QString error READ error NOTIFY changed)
  Q_PROPERTY(QVariantMap cleanup READ cleanup NOTIFY changed)
public:
  explicit DesktopConveniences(QObject *parent = nullptr);
  ~DesktopConveniences() override;
  bool dockInhibitRequested() const { return m_dockRequested; }
  bool dockInhibited() const { return m_lid.isValid(); }
  bool speakerTesting() const { return m_audio != nullptr; }
  bool cameraBlocked() const { return m_cameraBlocked; }
  bool busy() const { return m_busy; }
  QString error() const { return m_error; }
  QVariantMap cleanup() const { return m_cleanup; }
  void setDockInhibitRequested(bool requested);
  Q_INVOKABLE void testSpeaker(int channel);
  Q_INVOKABLE void stopSpeakerTest();
  Q_INVOKABLE void setCameraBlocked(bool blocked);
  Q_INVOKABLE void automaticCleanup(int days);
  Q_INVOKABLE void inspectCleanup();
  Q_INVOKABLE void clean(const QString &category, int olderDays = 30);
  Q_INVOKABLE void openPortal(const QString &uri,
                              const QString &language = QString());
  Q_INVOKABLE void closePortal();
  Q_INVOKABLE bool launch(const QString &application);
signals:
  void changed();
private slots:
  void sessionProperties(const QString &, const QVariantMap &,
                         const QStringList &);

private:
  void ensureSession();
  void fail(const QString &error);
  void cleanupJob(const QString &category, int days, bool remove);
  int m_busGeneration = 0;
  QString m_sessionPath;
  bool m_sessionActive = false, m_sessionPending = false;
  bool m_cameraBlocked = false;
  bool m_dockRequested = false, m_lidPending = false, m_busy = false;
  QDBusUnixFileDescriptor m_lid;
  QAudioSink *m_audio = nullptr;
  QBuffer *m_buffer = nullptr;
  QProcess *m_portal = nullptr;
  QString m_error;
  QVariantMap m_cleanup;
};
} // namespace hyprstack::services
