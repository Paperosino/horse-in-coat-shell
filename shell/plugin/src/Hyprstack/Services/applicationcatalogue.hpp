#pragma once
#include <QFileSystemWatcher>
#include <QHash>
#include <QObject>
#include <QQmlEngine>
#include <QTimer>
#include <QVariantMap>
#include <QSet>
#include <QtQmlIntegration/qqmlintegration.h>

namespace hyprstack::services {
class DesktopApplication : public QObject {
  Q_OBJECT
  QML_ELEMENT
  QML_UNCREATABLE("Applications are provided by ApplicationCatalogue")
#define APP_FIELD(type, field)                                                 \
Q_PROPERTY(type field READ field NOTIFY changed) public : type field() const { \
    return m_data.value(QString::fromLatin1(#field)).value<type>();            \
  }
  APP_FIELD(QString, id)
  APP_FIELD(QString, name)
  APP_FIELD(QString, icon)
  APP_FIELD(QString, genericName)
  APP_FIELD(QString, comment)
  APP_FIELD(QString, execString)
  APP_FIELD(QString, startupClass)
  APP_FIELD(QString, workingDirectory)
  APP_FIELD(QStringList, command)
  APP_FIELD(QStringList, categories)
  APP_FIELD(QStringList, keywords)
  APP_FIELD(bool, runInTerminal)
  APP_FIELD(bool, noDisplay)
#undef APP_FIELD
  Q_PROPERTY(QObjectList actions READ actions NOTIFY changed)
public:
  explicit DesktopApplication(QObject *parent = nullptr) : QObject(parent) {}
  QObjectList actions() const { return m_actions; }
  QString filePath() const { return m_path; }
  bool update(const QVariantMap &data, const QString &path, bool fileChanged = false);
  Q_INVOKABLE void execute();
  Q_INVOKABLE QString animationIcon();
  void invalidateIcon() { m_animationIcon.clear(); }
signals:
  void changed();
  void launchFailed(const QString &message);

private:
  QVariantMap m_data;
  QString m_path, m_animationIcon, m_iconTheme;
  QObjectList m_actions;
};
class DesktopApplicationAction : public QObject {
  Q_OBJECT
  QML_ELEMENT
  QML_UNCREATABLE("Actions belong to applications")
  Q_PROPERTY(QString name MEMBER m_name CONSTANT)
public:
  DesktopApplicationAction(QString path, QString id, QString name,
                           QObject *parent);
  Q_INVOKABLE void execute();

private:
  QString m_path, m_id, m_name;
};
class ApplicationCatalogue : public QObject {
  Q_OBJECT
  QML_ELEMENT
  QML_SINGLETON
  Q_PROPERTY(
      QVariantMap applications READ applications NOTIFY applicationsChanged)
  Q_PROPERTY(QString error READ error NOTIFY errorChanged)
  Q_PROPERTY(quint64 iconRevision READ iconRevision NOTIFY iconsChanged)
public:
  explicit ApplicationCatalogue(QObject *parent = nullptr);
  QVariantMap applications() const {
    return {{QStringLiteral("values"), QVariant::fromValue(m_visible)}};
  }
  QString error() const { return m_error; }
  quint64 iconRevision() const { return m_iconRevision; }
  Q_INVOKABLE QObject *byId(QString id) const;
  Q_INVOKABLE QObject *heuristicLookup(QString name) const;
  Q_INVOKABLE void refresh(bool force = false);
signals:
  void applicationsChanged();
  void errorChanged();
  void iconsChanged();

private:
  void scan(bool force);
  void watchIcons();
  void invalidateIcons();
  struct CachedFile { QByteArray stamp; QString tryExec, executable; };
  QHash<QString, CachedFile> m_cachedFiles;
  QSet<QString> m_dirtyFiles;
  QHash<QString, DesktopApplication *> m_entries;
  mutable QHash<QString, DesktopApplication *> m_lookupCache;
  QObjectList m_visible;
  QFileSystemWatcher m_watcher;
  QFileSystemWatcher m_iconWatcher;
  QTimer m_debounce, m_reconcile;
  QString m_error;
  QString m_watchedIconTheme;
  quint64 m_iconRevision = 0;
  bool m_iconsDirty = false;
};
} // namespace hyprstack::services
