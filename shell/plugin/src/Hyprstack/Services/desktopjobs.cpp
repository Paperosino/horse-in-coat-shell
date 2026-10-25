#include "desktopjobs.hpp"
#include <QCoreApplication>
#include <QDBusConnection>
#include <QDBusMessage>
#include <QDBusPendingCallWatcher>
#include <QDBusPendingReply>
#include <QDBusServiceWatcher>
#include <QJSEngine>
#include <QJsonDocument>
#include <QJsonObject>
#include <QQmlEngine>
namespace hyprstack::services {
using namespace Qt::StringLiterals;
namespace {
QDBusMessage call(const QString &method, QVariantList args = {}) {
  auto message = QDBusMessage::createMethodCall(u"org.hics.Desktop1"_s,
                                                u"/org/hics/Desktop1"_s,
                                                u"org.hics.Desktop1"_s, method);
  message.setArguments(args);
  return message;
}
QVariantMap decode(const QString &raw) {
  return QJsonDocument::fromJson(raw.toUtf8()).object().toVariantMap();
}
} // namespace
DesktopJobs::DesktopJobs(QObject *parent) : QObject(parent) {
  auto bus = QDBusConnection::sessionBus();
  bus.connect(u"org.hics.Desktop1"_s, u"/org/hics/Desktop1"_s,
              u"org.hics.Desktop1"_s, u"Changed"_s, this,
              SLOT(stateChanged(QString)));
  bus.connect(u"org.hics.Desktop1"_s, u"/org/hics/Desktop1"_s,
              u"org.hics.Desktop1"_s, u"Completed"_s, this,
              SLOT(completed(QString, QString)));
  auto *watcher =
      new QDBusServiceWatcher(u"org.hics.Desktop1"_s, bus,
                              QDBusServiceWatcher::WatchForOwnerChange, this);
  connect(
      watcher, &QDBusServiceWatcher::serviceOwnerChanged, this,
      [this](const QString &, const QString &, const QString &owner) {
        m_available = !owner.isEmpty();
        if (m_available)
          refresh();
        else {
          const auto pending = m_pending;
          m_pending.clear();
          for (const auto &request : pending)
            deliver(
                request,
                {{u"error"_s,
                  u"Desktop service restarted; inspect the operations centre"_s}});
        }
        emit changed();
      });
  refresh();
}
void DesktopJobs::deliver(const Pending &pending, const QVariantMap &result) {
  if (qjsEngine(this) && (!pending.guarded || pending.owner) &&
      pending.callback.isCallable())
    pending.callback.call({qjsEngine(this)->toScriptValue(result)});
}
void DesktopJobs::stateChanged(const QString &raw) {
  const auto value = decode(raw);
  m_jobs = value.value(u"jobs"_s).toList();
  m_comfort = value.value(u"comfort"_s).toMap();
  m_available = true;
  emit changed();
}
void DesktopJobs::refresh() {
  auto *watcher = new QDBusPendingCallWatcher(
      QDBusConnection::sessionBus().asyncCall(call(u"Status"_s), 5000), this);
  connect(watcher, &QDBusPendingCallWatcher::finished, this, [this, watcher] {
    QDBusPendingReply<QString> reply = *watcher;
    watcher->deleteLater();
    if (!reply.isError())
      stateChanged(reply.value());
    else {
      m_available = false;
      emit changed();
    }
  });
}
void DesktopJobs::request(const QString &operation, const QVariantMap &args,
                          QJSValue callback, QObject *owner) {
  Pending pending{callback, owner, owner != nullptr};
  const auto raw = QString::fromUtf8(
      QJsonDocument::fromVariant(args).toJson(QJsonDocument::Compact));
  auto *watcher =
      new QDBusPendingCallWatcher(QDBusConnection::sessionBus().asyncCall(
                                      call(u"Start"_s, {operation, raw}), 5000),
                                  this);
  connect(watcher, &QDBusPendingCallWatcher::finished, this,
          [this, watcher, pending] {
            QDBusPendingReply<QString> reply = *watcher;
            watcher->deleteLater();
            if (reply.isError()) {
              deliver(pending, {{u"error"_s, reply.error().message()}});
              return;
            }
            auto value = decode(reply.value());
            const auto id = value.value(u"id"_s).toString();
            if (id.isEmpty()) {
              deliver(pending, value);
              return;
            }
            m_pending[id] = pending;
            auto *result = new QDBusPendingCallWatcher(
                QDBusConnection::sessionBus().asyncCall(call(u"Result"_s, {id}),
                                                        5000),
                this);
            connect(result, &QDBusPendingCallWatcher::finished, this,
                    [this, result, id] {
                      QDBusPendingReply<QString> r = *result;
                      result->deleteLater();
                      if (r.isError()) {
                        if (m_pending.contains(id))
                          deliver(m_pending.take(id),
                                  {{u"error"_s, r.error().message()}});
                        return;
                      }
                      const auto resultData = decode(r.value());
                      if (resultData.value(u"finished"_s).toBool() ||
                          !resultData.value(u"error"_s).toString().isEmpty())
                        completed(id, r.value());
                    });
          });
}
void DesktopJobs::completed(const QString &id, const QString &raw) {
  if (!m_pending.contains(id))
    return;
  const auto pending = m_pending.take(id);
  auto response = decode(raw);
  auto value = response.value(u"result"_s).toMap();
  if (!response.value(u"error"_s).toString().isEmpty())
    value[u"error"_s] = response.value(u"error"_s);
  deliver(pending, value);
}
void DesktopJobs::details(const QString &id, QJSValue callback,
                          QObject *owner) {
  Pending pending{callback, owner, owner != nullptr};
  auto *watcher = new QDBusPendingCallWatcher(
      QDBusConnection::sessionBus().asyncCall(call(u"Result"_s, {id}), 5000),
      this);
  connect(watcher, &QDBusPendingCallWatcher::finished, this,
          [this, watcher, pending] {
            QDBusPendingReply<QString> reply = *watcher;
            watcher->deleteLater();
            deliver(pending,
                    reply.isError()
                        ? QVariantMap{{u"error"_s, reply.error().message()}}
                        : decode(reply.value()));
          });
}
void DesktopJobs::acknowledge(const QString &id) {
  QDBusConnection::sessionBus().asyncCall(call(u"Acknowledge"_s, {id}), 5000);
}
void DesktopJobs::report(const QString &source, const QString &operation,
                         const QString &phase, double progress,
                         const QString &error) {
  QDBusConnection::sessionBus().asyncCall(
      call(u"Report"_s, {source, operation, phase, progress,
                         QCoreApplication::applicationPid(), error}),
      5000);
}
void DesktopJobs::cancel(const QString &id) {
  QDBusConnection::sessionBus().asyncCall(call(u"Cancel"_s, {id}), 5000);
}
void DesktopJobs::retry(const QString &id) {
  QDBusConnection::sessionBus().asyncCall(call(u"Retry"_s, {id}), 5000);
}
} // namespace hyprstack::services
