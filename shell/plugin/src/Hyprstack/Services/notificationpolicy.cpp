#include "notificationpolicy.hpp"
#include <QDateTime>
#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QJsonDocument>
#include <QSaveFile>
#include <QStandardPaths>
#include <algorithm>
namespace hyprstack::services {
using namespace Qt::StringLiterals;
NotificationPolicy::NotificationPolicy(QObject *parent) : QObject(parent) {
    m_path = QStandardPaths::writableLocation(QStandardPaths::ConfigLocation) + u"/hics/notification-rules.json"_s;
    QFile f(m_path);
    if (f.exists()) {
        if (f.open(QIODevice::ReadOnly)) {
            QJsonParseError error;
            auto document = QJsonDocument::fromJson(f.readAll(), &error);
            if (error.error == QJsonParseError::NoError && document.isObject()) {
                m_apps = document.object()[u"applications"_s].toObject();
                m_until = document.object()[u"pausedUntil"_s].toVariant().toLongLong();
            } else m_error = tr("Unable to read notification rules");
        } else m_error = f.errorString();
    }
    m_saveTimer.setSingleShot(true); m_saveTimer.setInterval(250);
    connect(&m_saveTimer, &QTimer::timeout, this, &NotificationPolicy::save);
    m_expiry.setInterval(1000);
    connect(&m_expiry, &QTimer::timeout, this, [this] { if (!paused()) resume(); });
    if (paused()) m_expiry.start(); else m_until = 0;
}
NotificationPolicy::~NotificationPolicy() { if (m_saveTimer.isActive()) save(); }
QVariantList NotificationPolicy::applications() const {
    QVariantList result;
    for (auto it = m_apps.begin(); it != m_apps.end(); ++it) {
        auto row = it.value().toObject().toVariantMap(); row[u"id"_s] = it.key(); result.append(row);
    }
    return result;
}
bool NotificationPolicy::paused() const { return m_until > QDateTime::currentSecsSinceEpoch(); }
void NotificationPolicy::observe(const QString &id, const QString &name) {
    if (id.isEmpty() || id.size() > 512 || (m_apps.size() >= 500 && !m_apps.contains(id))) return;
    auto row = m_apps[id].toObject();
    if (row[u"name"_s].toString() == name && row.contains(u"mode"_s)) return;
    row[u"name"_s] = name.left(512);
    if (!row.contains(u"mode"_s)) row[u"mode"_s] = u"all"_s;
    m_apps[id] = row; m_saveTimer.start(); emit changed();
}
QString NotificationPolicy::rule(const QString &id) const {
    auto mode = m_apps[id].toObject()[u"mode"_s].toString();
    return QStringList{u"all"_s, u"silent"_s, u"blocked"_s}.contains(mode) ? mode : u"all"_s;
}
void NotificationPolicy::setRule(const QString &id, const QString &mode) {
    if (!m_apps.contains(id) || !QStringList{u"all"_s, u"silent"_s, u"blocked"_s}.contains(mode)) return;
    auto row = m_apps[id].toObject(); row[u"mode"_s] = mode; m_apps[id] = row;
    save(); emit changed();
}
void NotificationPolicy::pauseFor(int minutes) {
    m_until = QDateTime::currentSecsSinceEpoch() + std::clamp(minutes, 1, 1440) * 60;
    m_expiry.start(); save(); emit changed();
}
void NotificationPolicy::resume() { m_until = 0; m_expiry.stop(); save(); emit changed(); }
void NotificationPolicy::save() {
    m_saveTimer.stop();
    if (!QDir().mkpath(QFileInfo(m_path).absolutePath())) { m_error = tr("Unable to create notification settings directory"); emit changed(); return; }
    QSaveFile file(m_path);
    if (!file.open(QIODevice::WriteOnly)) { m_error = file.errorString(); emit changed(); return; }
    file.setPermissions(QFileDevice::ReadOwner | QFileDevice::WriteOwner);
    auto bytes = QJsonDocument(QJsonObject{{u"version"_s, 1}, {u"applications"_s, m_apps}, {u"pausedUntil"_s, m_until}}).toJson();
    if (file.write(bytes) != bytes.size() || !file.commit()) { m_error = file.errorString(); emit changed(); }
}
}
