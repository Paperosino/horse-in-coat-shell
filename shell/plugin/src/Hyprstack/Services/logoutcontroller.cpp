#include "logoutcontroller.hpp"

#include <qdbusconnection.h>
#include <qdbusmessage.h>
#include <qdbusextratypes.h>
#include <qdbusservicewatcher.h>
#include <quuid.h>
#include <qdbuspendingcall.h>
#include <qdbuspendingreply.h>
#include <qjsondocument.h>
#include <qjsonarray.h>
#include <qjsonobject.h>

namespace hyprstack::services {
namespace {
using Qt::StringLiterals::operator""_s;
const QString service = u"org.freedesktop.impl.portal.desktop.hics"_s;
const QString path = u"/org/freedesktop/portal/desktop"_s;
const QString iface = u"org.hics.Logout1"_s;
QDBusMessage message(const QString& method, const QVariantList& args = {}) {
    auto msg = QDBusMessage::createMethodCall(service, path, iface, method);
    msg.setArguments(args);
    return msg;
}
}

LogoutController::LogoutController(QObject* parent) : QObject(parent) {
    auto bus = QDBusConnection::sessionBus();
    m_owned = bus.registerService(u"org.hics.LogoutController"_s);
    auto* frontend = new QDBusServiceWatcher(u"org.freedesktop.portal.Desktop"_s, bus,
        QDBusServiceWatcher::WatchForOwnerChange, this);
    connect(frontend, &QDBusServiceWatcher::serviceOwnerChanged, this,
        [this](const QString&, const QString& oldOwner, const QString& newOwner) {
            if (!oldOwner.isEmpty() && oldOwner != newOwner && m_active) {
                m_frontendLost = true; m_ready = false; m_timer.stop();
                setFailure(u"Desktop portal disconnected during logout"_s);
            }
        });
    auto* backend = new QDBusServiceWatcher(service, bus, QDBusServiceWatcher::WatchForOwnerChange, this);
    connect(backend, &QDBusServiceWatcher::serviceOwnerChanged, this,
        [this](const QString&, const QString& oldOwner, const QString& newOwner) {
            if (!oldOwner.isEmpty() && oldOwner != newOwner && m_active) {
                m_backendLost = true; m_ready = false; m_timer.stop();
                setFailure(u"Logout portal disconnected during logout"_s);
            }
        });
    m_timer.setInterval(250);
    connect(&m_timer, &QTimer::timeout, this, &LogoutController::refresh);
}

LogoutController::~LogoutController() {
    if (m_owned) QDBusConnection::sessionBus().unregisterService(u"org.hics.LogoutController"_s);
}

void LogoutController::setLocked(bool value) {
    if (m_locked == value) return;
    m_locked = value;
    if (m_owned) QDBusConnection::sessionBus().asyncCall(message(u"SetLocked"_s, {value}));
    if (value && m_active) cancel();
    emit changed();
}

void LogoutController::request() {
    if (m_locked || m_active || m_busy) return;
    m_active = true; m_ready = false; m_frontendLost = false; m_backendLost = false; m_blockers.clear(); m_error.clear();
    if (!m_owned) { setFailure(u"Session controller is unavailable"_s); return; }
    m_busy = true; const auto epoch = ++m_epoch; emit changed();
    auto* watcher = new QDBusPendingCallWatcher(QDBusConnection::sessionBus().asyncCall(message(u"SetLocked"_s, {false})), this);
    connect(watcher, &QDBusPendingCallWatcher::finished, this, [this, epoch](QDBusPendingCallWatcher* self) {
        const QDBusPendingReply<> reply = *self; self->deleteLater();
        if (epoch != m_epoch || !m_active || m_frontendLost || m_backendLost) { m_busy = false; emit changed(); return; }
        if (reply.isError()) { m_busy = false; setFailure(reply.error().message()); return; }
        startProbe(epoch);
    });
}

void LogoutController::startProbe(quint64 epoch) {
    m_probeReason = u"hics-logout-probe-"_s + QUuid::createUuid().toString(QUuid::WithoutBraces);
    auto msg = QDBusMessage::createMethodCall(u"org.freedesktop.portal.Desktop"_s, path,
                                               u"org.freedesktop.portal.Inhibit"_s, u"Inhibit"_s);
    msg.setArguments({QString(), uint(1), QVariantMap{{u"reason"_s, m_probeReason}}});
    auto* watcher = new QDBusPendingCallWatcher(QDBusConnection::sessionBus().asyncCall(msg), this);
    connect(watcher, &QDBusPendingCallWatcher::finished, this, [this, epoch](QDBusPendingCallWatcher* self) {
        const QDBusPendingReply<QDBusObjectPath> reply = *self; self->deleteLater();
        if (!reply.isError()) m_probePath = reply.value().path();
        if (epoch != m_epoch || !m_active || m_frontendLost || m_backendLost) {
            closeProbe(); m_busy = false; emit changed(); return;
        }
        if (reply.isError()) { m_busy = false; setFailure(reply.error().message()); return; }
        checkProbe(epoch, 30);
    });
}

void LogoutController::checkProbe(quint64 epoch, int attempts) {
    if (epoch != m_epoch || !m_active || m_frontendLost || m_backendLost) {
        closeProbe(); m_busy = false; emit changed(); return;
    }
    auto* watcher = new QDBusPendingCallWatcher(QDBusConnection::sessionBus().asyncCall(message(u"List"_s)), this);
    connect(watcher, &QDBusPendingCallWatcher::finished, this, [this, epoch, attempts](QDBusPendingCallWatcher* self) {
        const QDBusPendingReply<QString> reply = *self; self->deleteLater();
        if (epoch != m_epoch || !m_active || m_frontendLost || m_backendLost) {
            closeProbe(); m_busy = false; emit changed(); return;
        }
        if (reply.isError()) { closeProbe(); m_busy = false; setFailure(reply.error().message()); return; }
        const auto data = QJsonDocument::fromJson(reply.value().toUtf8());
        if (!data.isArray()) { closeProbe(); m_busy = false; setFailure(u"Invalid portal response"_s); return; }
        for (const auto& value : data.array()) {
            if (value.toObject().value(u"reason"_s).toString() == m_probeReason) {
                closeProbe(); beginQuery(epoch); return;
            }
        }
        if (attempts <= 1) {
            closeProbe(); m_busy = false; setFailure(u"Desktop portal did not forward logout inhibition"_s); return;
        }
        QTimer::singleShot(100, this, [this, epoch, attempts] { checkProbe(epoch, attempts - 1); });
    });
}

void LogoutController::closeProbe() {
    if (m_probePath.isEmpty()) return;
    auto msg = QDBusMessage::createMethodCall(u"org.freedesktop.portal.Desktop"_s, m_probePath,
                                               u"org.freedesktop.portal.Request"_s, u"Close"_s);
    m_probePath.clear();
    QDBusConnection::sessionBus().asyncCall(msg);
}

void LogoutController::beginQuery(quint64 epoch) {
    auto* watcher = new QDBusPendingCallWatcher(QDBusConnection::sessionBus().asyncCall(message(u"BeginQuery"_s)), this);
    connect(watcher, &QDBusPendingCallWatcher::finished, this, [this, epoch](QDBusPendingCallWatcher* self) {
        const QDBusPendingReply<> reply = *self; self->deleteLater();
        if (epoch != m_epoch || !m_active) {
            if (!reply.isError()) { m_queryStarted = true; abortQuery(); }
            else { m_busy = false; emit changed(); }
            return;
        }
        m_busy = false;
        if (reply.isError()) { setFailure(reply.error().message()); return; }
        m_queryStarted = true;
        if (!m_frontendLost && !m_backendLost) { m_timer.start(); refresh(); }
        emit changed();
    });
}

void LogoutController::refresh() {
    if (!m_active || m_locked || (m_frontendLost || m_backendLost) || !m_queryStarted || m_refreshing || m_busy) return;
    m_refreshing = true; const auto epoch = m_epoch;
    auto* watcher = new QDBusPendingCallWatcher(QDBusConnection::sessionBus().asyncCall(message(u"List"_s)), this);
    connect(watcher, &QDBusPendingCallWatcher::finished, this, [this, epoch](QDBusPendingCallWatcher* self) {
        const QDBusPendingReply<QString> reply = *self; self->deleteLater();
        if (epoch != m_epoch || !m_active || m_frontendLost || m_backendLost) { m_refreshing = false; return; }
        if (reply.isError()) { m_refreshing = false; setFailure(reply.error().message()); return; }
        QJsonParseError error;
        const auto data = QJsonDocument::fromJson(reply.value().toUtf8(), &error);
        if (error.error != QJsonParseError::NoError || !data.isArray()) {
            m_refreshing = false; setFailure(u"Invalid portal response"_s); return;
        }
        m_blockers.clear();
        for (const auto& item : data.array()) {
            const auto entry = item.toObject().toVariantMap();
            if (m_probeReason.isEmpty() || entry.value(u"reason"_s).toString() != m_probeReason) m_blockers.append(entry);
        }
        auto* next = new QDBusPendingCallWatcher(QDBusConnection::sessionBus().asyncCall(message(u"Ready"_s)), this);
        connect(next, &QDBusPendingCallWatcher::finished, this, [this, epoch](QDBusPendingCallWatcher* done) {
            const QDBusPendingReply<bool> state = *done; done->deleteLater(); m_refreshing = false;
            if (epoch != m_epoch || !m_active || m_frontendLost || m_backendLost) return;
            if (state.isError()) { setFailure(state.error().message()); return; }
            m_ready = state.value(); m_error.clear(); emit changed();
        });
    });
}

void LogoutController::setFailure(const QString& text) {
    m_ready = false; m_error = text; emit changed();
}

void LogoutController::abortQuery() {
    m_busy = true;
    auto* watcher = new QDBusPendingCallWatcher(QDBusConnection::sessionBus().asyncCall(message(u"Cancel"_s)), this);
    connect(watcher, &QDBusPendingCallWatcher::finished, this, [this](QDBusPendingCallWatcher* self) {
        self->deleteLater(); m_queryStarted = false; m_busy = false; emit changed();
    });
}

void LogoutController::reset() {
    ++m_epoch; closeProbe(); m_probeReason.clear(); m_timer.stop(); m_finishing = false; m_active = false; m_ready = false; m_blockers.clear(); m_error.clear(); emit changed();
}

void LogoutController::cancel() {
    if (!m_active || (m_finishing && !m_locked)) return;
    const bool started = m_queryStarted; reset();
    if (started) abortQuery();
}

void LogoutController::commit() {
    if (!m_active || !m_ready || m_busy || m_locked || (m_frontendLost || m_backendLost) || !m_queryStarted) return;
    m_busy = true; m_finishing = true; m_timer.stop(); const auto epoch = m_epoch; emit changed();
    auto* watcher = new QDBusPendingCallWatcher(QDBusConnection::sessionBus().asyncCall(message(u"Commit"_s)), this);
    connect(watcher, &QDBusPendingCallWatcher::finished, this, [this, epoch](QDBusPendingCallWatcher* self) {
        const QDBusPendingReply<> reply = *self; self->deleteLater();
        // A later cancellation or request owns the state now.
        if (epoch != m_epoch || !m_active || m_locked) return;
        m_finishing = false; m_busy = false;
        if (reply.isError()) { m_timer.start(); setFailure(reply.error().message()); return; }
        m_queryStarted = false; reset(); emit exitApproved();
    });
}

void LogoutController::force() {
    if (!m_active || m_busy || m_locked) return;
    if (!m_queryStarted || m_backendLost) { m_queryStarted = false; reset(); emit exitApproved(); return; }
    m_busy = true; m_finishing = true; m_timer.stop(); const auto epoch = m_epoch; emit changed();
    auto* watcher = new QDBusPendingCallWatcher(QDBusConnection::sessionBus().asyncCall(message(u"Force"_s)), this);
    connect(watcher, &QDBusPendingCallWatcher::finished, this, [this, epoch](QDBusPendingCallWatcher* self) {
        const QDBusPendingReply<> reply = *self; self->deleteLater();
        // A later cancellation or request owns the state now.
        if (epoch != m_epoch || !m_active || m_locked) return;
        m_finishing = false; m_busy = false;
        if (reply.isError()) { m_timer.start(); setFailure(reply.error().message()); return; }
        m_queryStarted = false; reset(); emit exitApproved();
    });
}
void LogoutController::terminationFailed(const QString& reason) {
    m_active = true; m_ready = false; m_busy = true; m_queryStarted = false;
    m_error = reason; const auto epoch = ++m_epoch; emit changed();
    auto* watcher = new QDBusPendingCallWatcher(QDBusConnection::sessionBus().asyncCall(message(u"AbortEnding"_s)), this);
    connect(watcher, &QDBusPendingCallWatcher::finished, this, [this, epoch](QDBusPendingCallWatcher* self) {
        self->deleteLater(); m_busy = false;
        if (epoch == m_epoch) emit changed();
    });
}

}
