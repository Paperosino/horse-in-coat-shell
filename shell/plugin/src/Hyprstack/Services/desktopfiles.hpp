#pragma once
#include <QFileSystemWatcher>
#include <QObject>
#include <QThreadPool>
#include <QTimer>
#include <QVariantList>
#include <QtQmlIntegration/qqmlintegration.h>
namespace hyprstack::services {
// One shared, event-driven view of XDG_DESKTOP_DIR, irrespective of the FM.
class DesktopFiles : public QObject {
  Q_OBJECT
  QML_ELEMENT
  QML_SINGLETON
  Q_PROPERTY(bool active READ active WRITE setActive NOTIFY changed)
  Q_PROPERTY(bool showHidden READ showHidden WRITE setShowHidden NOTIFY changed)
  Q_PROPERTY(QString directory READ directory NOTIFY changed)
  Q_PROPERTY(QString directoryUrl READ directoryUrl NOTIFY changed)
  Q_PROPERTY(QVariantList entries READ entries NOTIFY changed)
  Q_PROPERTY(QVariantMap positions READ positions NOTIFY changed)
  Q_PROPERTY(QString error READ error NOTIFY changed)
  Q_PROPERTY(bool loading READ loading NOTIFY changed)
public:
  explicit DesktopFiles(QObject *parent = nullptr);
  ~DesktopFiles() override;
  bool active() const { return m_active; }
  bool showHidden() const { return m_hidden; }
  bool loading() const { return m_scanning; }
  QString directory() const { return m_directory; }
  QString directoryUrl() const;
  QVariantMap positions() const { return m_positions; }
  QString error() const { return m_error; }
  QVariantList entries() const { return m_entries; }
  void setActive(bool);
  void setShowHidden(bool);
  Q_INVOKABLE void refresh();
  Q_INVOKABLE void place(const QString &output, const QString &url, int column,
                         int row);
  Q_INVOKABLE void tidy();
  Q_INVOKABLE void open(const QString &url);
  Q_INVOKABLE void reveal(const QString &url, bool properties = false);
  Q_INVOKABLE void copy(const QStringList &urls, bool cut = false);
  Q_INVOKABLE QVariantMap clipboardFiles() const;
  Q_INVOKABLE void releaseCut(const QStringList &sources);

private:
  void launch(const QString &, const QStringList &);
  void schedule();
  bool m_active = false, m_hidden = false, m_scanning = false, m_again = false;
  QString m_directory, m_error;
  QVariantList m_entries;
  QVariantMap m_positions;
  QFileSystemWatcher m_watch;
  QTimer m_debounce;
  QThreadPool m_pool;
signals:
  void changed();
};
} // namespace hyprstack::services
