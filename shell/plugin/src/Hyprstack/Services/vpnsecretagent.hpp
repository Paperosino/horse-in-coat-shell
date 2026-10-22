#pragma once
#include <QDBusContext>
#include <QDBusMessage>
#include <QDBusObjectPath>
#include <QObject>
#include <QPointer>
#include <QProcess>
#include <QQmlEngine>
#include <QVariantMap>
using VpnSettings = QMap<QString, QVariantMap>;
Q_DECLARE_METATYPE(VpnSettings)
namespace hyprstack::services {
class VpnSecretAgent : public QObject, protected QDBusContext {
  Q_OBJECT
  Q_CLASSINFO("D-Bus Interface", "org.freedesktop.NetworkManager.SecretAgent")
  QML_ELEMENT
  QML_SINGLETON
  Q_PROPERTY(QVariantMap challenge READ challenge NOTIFY changed)
  Q_PROPERTY(QString error READ error NOTIFY changed)
public:
  explicit VpnSecretAgent(QObject *parent = nullptr);
  QVariantMap challenge() const { return m_challenge; }
  QString error() const { return m_error; }
  Q_INVOKABLE void submit(const QVariantMap &values, bool remember);
  Q_INVOKABLE void cancel();
  Q_INVOKABLE void registerAgent();
signals:
  void changed();
public slots:
  VpnSettings GetSecrets(const VpnSettings &connection,
                         const QDBusObjectPath &path, const QString &setting,
                         const QStringList &hints, uint flags);
  void CancelGetSecrets(const QDBusObjectPath &path, const QString &setting);
  void SaveSecrets(const VpnSettings &connection, const QDBusObjectPath &path);
  void DeleteSecrets(const VpnSettings &connection,
                     const QDBusObjectPath &path);

private:
  QVariantMap m_challenge;
  QString m_error, m_owner, m_setting, m_uuid, m_path;
  QDBusMessage m_pending;
  quint64 m_request = 0;
  bool m_waiting = false;
  QMap<QString, QVariantMap> m_session;
  QPointer<QProcess> m_helper;
  QVariantMap m_helperValues;
  bool startPluginAuthentication(const VpnSettings &, const QStringList &,
                                 uint);
  bool authorized();
  void reply(const QVariantMap &values);
};
} // namespace hyprstack::services
