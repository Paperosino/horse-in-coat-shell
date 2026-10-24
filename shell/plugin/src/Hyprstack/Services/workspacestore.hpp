#pragma once
#include <QByteArray>
#include <memory>
#include <atomic>
#include <QStringList>
#include <QVariantList>
#include <QVariantMap>

namespace hics::workspace {
// Worker-local cancellation; never references the owning QObject.
extern thread_local std::shared_ptr<std::atomic_bool> commandCancellation;
QString configPath();
QString statePath();
QString startupPath();
QVariantMap readMap(const QString &path);
void writeMap(const QString &path, const QVariantMap &value);
QVariantMap defaults(const QString &group);
QVariantMap settings(const QString &group);
void setSettings(const QString &group, const QVariantMap &value);
QByteArray command(const QString &program, const QStringList &args,
                   int timeout = 5000);
QVariantList clipboardEntries(bool prune = true);
bool storeClipboard(const QByteArray &bytes, const QString &mime,
                    const QString &application = {},
                    bool explicitAction = false);
QString clipboardFile(const QString &id);
QByteArray clipboardData(const QString &id);
void alterClipboard(const QString &id, const QString &operation);
void clearClipboard(bool keepPinned);
QString clipboardDirectory();
QString normalizedChord(const QString &value);
QString luaString(const QString &value);
} // namespace hics::workspace
