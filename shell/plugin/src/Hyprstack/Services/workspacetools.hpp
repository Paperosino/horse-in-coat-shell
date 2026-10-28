#pragma once
#include "util/watchedprocess.hpp"
#include <QFileSystemWatcher>
#include <QFuture>
#include <QObject>
#include <QProcess>
#include <QQmlEngine>
#include <QTimer>
#include <QUrl>
#include <QVariantList>
#include <QVariantMap>
#include <atomic>
#include <functional>
#include <memory>

namespace hyprstack::services {
class ClipboardHistory : public QObject {
  Q_OBJECT
  QML_ELEMENT
  QML_SINGLETON
  Q_PROPERTY(QVariantMap settings READ settings NOTIFY changed)
  Q_PROPERTY(QVariantList entries READ entries NOTIFY changed)
  Q_PROPERTY(QString error READ error NOTIFY changed)
  Q_PROPERTY(bool capturing READ capturing NOTIFY changed)
  Q_PROPERTY(bool busy READ busy NOTIFY changed)
public:
  explicit ClipboardHistory(QObject *parent = nullptr);
  QVariantMap settings() const { return m_settings; }
  QVariantList entries() const { return m_entries; }
  QString error() const { return m_error; }
  bool busy() const { return m_importing; }
  bool capturing() const {
    return m_text->running() || m_image->running();
  }
  Q_INVOKABLE void refresh();
  Q_INVOKABLE void configure(const QVariantMap &values);
  Q_INVOKABLE void setLocked(bool locked);
  Q_INVOKABLE void copy(const QString &id);
  Q_INVOKABLE void pasteLatest();
  Q_INVOKABLE QString decode(const QString &id);
  Q_INVOKABLE void edit(const QString &id, const QString &value);
  Q_INVOKABLE void remove(const QString &id);
  Q_INVOKABLE void pin(const QString &id);
  Q_INVOKABLE void clear(bool keepPinned = true);
  Q_INVOKABLE void importLegacy();
  Q_INVOKABLE void prepareLogout();
signals:
  void changed();

private:
  void watchers();
  void perform(const std::function<void()> &action);
  QVariantMap m_settings;
  QVariantList m_entries;
  QString m_error;
  bool m_locked = false, m_importing = false;
  bool m_refreshing = false, m_refreshAgain = false;
  std::unique_ptr<hics::util::WatchedProcess> m_text, m_image;
  QFileSystemWatcher m_files;
  QTimer m_refresh;
};

class ShortcutEditor : public QObject {
  Q_OBJECT
  QML_ELEMENT
  QML_SINGLETON
  Q_PROPERTY(QVariantList actions READ actions NOTIFY changed)
  Q_PROPERTY(QVariantMap settings READ settings NOTIFY changed)
  Q_PROPERTY(QString error READ error NOTIFY changed)
public:
  explicit ShortcutEditor(QObject *parent = nullptr);
  QVariantList actions() const { return m_actions; }
  QVariantMap settings() const { return m_settings; }
  QString error() const { return m_error; }
  Q_INVOKABLE void refresh();
  Q_INVOKABLE QVariantList conflicts(const QString &id, const QString &chord,
                                     const QString &submap = QString()) const;
  Q_INVOKABLE QString recordKey(int key, int modifiers,
                                int nativeScanCode = 0) const;
  Q_INVOKABLE void save(const QVariantMap &action);
  Q_INVOKABLE void reset(const QString &id);
  Q_INVOKABLE void resetAll();
  Q_INVOKABLE void exportFile(const QUrl &url);
  Q_INVOKABLE void importFile(const QUrl &url);
  Q_INVOKABLE void configure(const QVariantMap &values);
signals:
  void changed();

private:
  void persist(const QVariantMap &settings);
  QVariantMap m_settings;
  bool m_attemptedReload = false;
  QVariantList m_actions;
  QString m_error;
};

class WorkspaceSession : public QObject {
  Q_OBJECT
  QML_ELEMENT
  QML_SINGLETON
  Q_PROPERTY(QVariantMap settings READ settings NOTIFY changed)
  Q_PROPERTY(QVariantList snapshots READ snapshots NOTIFY changed)
  Q_PROPERTY(QVariantMap preview READ preview NOTIFY changed)
  Q_PROPERTY(QVariantList report READ report NOTIFY changed)
  Q_PROPERTY(QString error READ error NOTIFY changed)
  Q_PROPERTY(bool busy READ busy NOTIFY changed)
  Q_PROPERTY(bool startupPending READ startupPending NOTIFY changed)
  Q_PROPERTY(QString desktop READ desktop CONSTANT)
public:
  explicit WorkspaceSession(QObject *parent = nullptr);
  ~WorkspaceSession() override;
  QVariantMap settings() const { return m_settings; }
  QVariantList snapshots() const { return m_snapshots; }
  QVariantMap preview() const { return m_preview; }
  QVariantList report() const { return m_report; }
  QString error() const { return m_error; }
  bool busy() const { return m_busy; }
  bool startupPending() const { return m_startupPending; }
  QString desktop() const;
  Q_INVOKABLE void refresh();
  Q_INVOKABLE void configure(const QVariantMap &values);
  Q_INVOKABLE void capture(const QString &name, bool automatic = false);
  Q_INVOKABLE void captureProject(const QString &name, int sourceWorkspace, int targetWorkspace, const QString &mode, bool keepTheme);
  Q_INVOKABLE void inspect(const QString &id);
  Q_INVOKABLE void savePreview(const QVariantMap &snapshot);
  Q_INVOKABLE void remove(const QString &id);
  Q_INVOKABLE void restore(const QString &id,
                           const QVariantList &selected = QVariantList());
  Q_INVOKABLE void cancel();
  Q_INVOKABLE QVariantList desktopSessions() const;
  Q_INVOKABLE void importDesktop(const QString &source);
  Q_INVOKABLE void importFile(const QUrl &url);
  Q_INVOKABLE void exportFile(const QString &id, const QUrl &url,
                              bool portable = false);
  Q_INVOKABLE void dismissStartup();
  static void saveBeforeExit();
  static void checkpointBeforeExit();
  static void clearClipboardBeforeExit();
signals:
  void changed();
  void finished(bool success);

private:
  void task(const std::function<QVariantMap()> &work,
            const std::function<void(const QVariantMap &)> &done);
  void autostart();
  QVariantMap m_settings, m_preview;
  QVariantList m_snapshots, m_report;
  QString m_error;
  QString m_refreshError;
  bool m_busy = false, m_startupPending = false;
  QFuture<QVariantMap> m_task;
  QFileSystemWatcher m_sessionFiles;
  QTimer m_refreshTimer;
  std::shared_ptr<std::atomic_bool> m_cancel =
      std::make_shared<std::atomic_bool>(false);
};
} // namespace hyprstack::services
