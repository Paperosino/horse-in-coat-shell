#pragma once
#include <QObject>
#include <QFuture>
#include <QQmlEngine>
#include <QVariantList>
#include <QVariantMap>
#include <functional>
#include <memory>
namespace hyprstack::services {
class NetworkManagerVpn : public QObject {
  Q_OBJECT
  QML_ELEMENT
  QML_SINGLETON
  Q_PROPERTY(bool busy READ busy NOTIFY changed)
  Q_PROPERTY(bool canCancel READ canCancel NOTIFY changed)
  Q_PROPERTY(QString error READ error NOTIFY changed)
  Q_PROPERTY(QVariantList plugins READ plugins NOTIFY changed)
  Q_PROPERTY(QVariantList profiles READ profiles NOTIFY changed)
  Q_PROPERTY(QVariantMap draft READ draft NOTIFY draftChanged)
public:
  explicit NetworkManagerVpn(QObject *parent = nullptr);
  ~NetworkManagerVpn() override;
  bool busy() const { return m_busy; }
  bool canCancel() const { return m_busy && m_canCancel; }
  QString error() const { return m_error; }
  QVariantList plugins() const { return m_plugins; }
  QVariantList profiles() const { return m_profiles; }
  QVariantMap draft() const { return m_draft; }
  Q_INVOKABLE void refresh();
  Q_INVOKABLE void cancel();
  Q_INVOKABLE QString generateWireGuardKey() const;
  Q_INVOKABLE void installPlugin(const QString &id);
  Q_INVOKABLE void create(const QString &service);
  Q_INVOKABLE void edit(const QString &path);
  Q_INVOKABLE void save(const QVariantMap &draft);
  Q_INVOKABLE void remove(const QString &path);
  Q_INVOKABLE void activate(const QString &path);
  Q_INVOKABLE void deactivate(const QString &activePath);
  Q_INVOKABLE void importFile(const QString &service, const QUrl &file);
  Q_INVOKABLE void exportFile(const QString &path, const QUrl &file);
  Q_INVOKABLE QVariantMap validate(const QVariantMap &draft) const;
  Q_INVOKABLE void discard();
signals:
  void changed();
  void draftChanged();
  void saved(const QString &path);
  void operationSucceeded();

private:
  struct State;
  std::shared_ptr<State> m_state;
  bool m_busy = false;
  bool m_canCancel = true;
  QString m_error;
  bool m_refreshError = false;
  QVariantList m_plugins, m_profiles;
  QVariantMap m_draft;
  QString m_activationPath;
  bool m_vpnFailureReceived = false;
  void run(std::function<QVariantMap()> task,
           std::function<void(const QVariantMap &)> done,
           bool clearError = true, bool cancellable = true);
private slots:
  void activationStateChanged(uint state, uint reason);
  void vpnStateChanged(uint state, uint reason);
};
} // namespace hyprstack::services
