#include "desktopfiles.hpp"
#include "util/applicationlaunch.hpp"
#include <QClipboard>
#include <QDBusConnection>
#include <QDBusMessage>
#include <QDBusPendingCallWatcher>
#include <QDBusPendingReply>
#include <QDirIterator>
#include <QFileInfo>
#include <QFutureWatcher>
#include <QGuiApplication>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QMimeData>
#include <QMimeDatabase>
#include <QSaveFile>
#include <QStandardPaths>
#include <QUrl>
#include <QtConcurrent>
#include <unistd.h>
#include <utility>
#pragma push_macro("signals")
#undef signals
#include <gio/gdesktopappinfo.h>
#pragma pop_macro("signals")
using namespace Qt::StringLiterals;
namespace hyprstack::services {
DesktopFiles::DesktopFiles(QObject *p) : QObject(p) {
  m_pool.setMaxThreadCount(1);
  m_pool.setExpiryTimeout(1000);
  m_debounce.setSingleShot(true);
  m_debounce.setInterval(150);
  connect(&m_debounce, &QTimer::timeout, this, &DesktopFiles::refresh);
  connect(&m_watch, &QFileSystemWatcher::directoryChanged, this,
          &DesktopFiles::schedule);
  connect(&m_watch, &QFileSystemWatcher::fileChanged, this,
          &DesktopFiles::schedule);
}
DesktopFiles::~DesktopFiles() {
  m_pool.clear();
  m_pool.waitForDone();
}
QString DesktopFiles::directoryUrl() const {
  return QUrl::fromLocalFile(m_directory).toString(QUrl::FullyEncoded);
}
void DesktopFiles::setActive(bool value) {
  if (m_active == value)
    return;
  m_active = value;
  if (value) {
    QFile file(
        (QStandardPaths::writableLocation(QStandardPaths::ConfigLocation) +
         u"/hics"_s) +
        u"/desktop-icons.json"_s);
    m_positions.clear();
    if (file.open(QIODevice::ReadOnly) && file.size() < 1024 * 1024) {
      const auto screens = QJsonDocument::fromJson(file.readAll()).object();
      for (auto screen = screens.begin();
           screen != screens.end() && m_positions.size() < 32; ++screen) {
        if (screen.key().size() > 256 || !screen.value().isObject())
          continue;
        QVariantMap clean;
        const auto values = screen.value().toObject();
        for (auto item = values.begin();
             item != values.end() && clean.size() < 2000; ++item) {
          const auto position = item.value().toArray();
          if (item.key().isEmpty() || item.key().contains(u'/') ||
              position.size() != 2)
            continue;
          const auto x = position[0].toInt(-1), y = position[1].toInt(-1);
          if (x < 0 || x > 1000 || y < 0 || y > 1000 ||
              !qFuzzyCompare(position[0].toDouble() + 1, double(x) + 1) ||
              !qFuzzyCompare(position[1].toDouble() + 1, double(y) + 1))
            continue;
          clean.insert(item.key(), QVariantList{x, y});
        }
        m_positions.insert(screen.key(), clean);
      }
    }
    refresh();
  } else {
    m_debounce.stop();
    if (!m_watch.directories().isEmpty())
      m_watch.removePaths(m_watch.directories());
    if (!m_watch.files().isEmpty())
      m_watch.removePaths(m_watch.files());
    m_entries.clear();
  }
  emit changed();
}
void DesktopFiles::setShowHidden(bool value) {
  if (m_hidden == value)
    return;
  m_hidden = value;
  refresh();
  emit changed();
}
void DesktopFiles::schedule() {
  if (m_active)
    m_debounce.start();
}
void DesktopFiles::refresh() {
  if (!m_active)
    return;
  if (m_scanning) {
    m_again = true;
    return;
  }
  // Qt caches user-dirs per call, so changes from xdg-user-dirs are observed.
  m_directory =
      QStandardPaths::writableLocation(QStandardPaths::DesktopLocation);
  if (!m_watch.directories().isEmpty())
    m_watch.removePaths(m_watch.directories());
  if (!m_watch.files().isEmpty())
    m_watch.removePaths(m_watch.files());
  const auto config =
      QStandardPaths::writableLocation(QStandardPaths::ConfigLocation);
  QStringList dirs{config};
  // Disabled XDG desktop (HOME) must never expose the whole home directory.
  if (!m_directory.isEmpty() &&
      QDir::cleanPath(m_directory) != QDir::homePath()) {
    dirs << (QFileInfo(m_directory).isDir()
                 ? m_directory
                 : QFileInfo(m_directory).absolutePath());
  }
  for (const auto &path : dirs)
    if (QFileInfo(path).isDir())
      m_watch.addPath(path);
  if (QFileInfo::exists(config + u"/user-dirs.dirs"_s))
    m_watch.addPath(config + u"/user-dirs.dirs"_s);
  m_scanning = true;
  emit changed();
  const auto dir = m_directory;
  const bool hidden = m_hidden;
  auto *watcher = new QFutureWatcher<QVariantMap>(this);
  connect(watcher, &QFutureWatcher<QVariantMap>::finished, this,
          [this, watcher, dir, hidden] {
            const auto result = watcher->result();
            watcher->deleteLater();
            m_scanning = false;
            if (m_active && dir == m_directory && hidden == m_hidden) {
              m_entries = result.value(u"entries"_s).toList();
              m_error = result.value(u"error"_s).toString();
              QSet<QString> names;
              for (const auto &entry : m_entries)
                names.insert(entry.toMap().value(u"fileName"_s).toString());
              for (auto it = m_positions.begin(); it != m_positions.end();
                   ++it) {
                auto screen = it.value().toMap();
                for (auto item = screen.begin(); item != screen.end();)
                  if (!names.contains(item.key()))
                    item = screen.erase(item);
                  else
                    ++item;
                it.value() = screen;
              }
            }
            emit changed();
            if (std::exchange(m_again, false))
              refresh();
          });
  watcher->setFuture(QtConcurrent::run(&m_pool, [dir, hidden] {
    QVariantList entries;
    QString error;
    if (dir.isEmpty() || QDir::cleanPath(dir) == QDir::homePath() ||
        (!QFileInfo(dir).canonicalFilePath().isEmpty() &&
         QFileInfo(dir).canonicalFilePath() ==
             QFileInfo(QDir::homePath()).canonicalFilePath()))
      error =
          u"The XDG desktop folder is disabled. Choose a separate desktop folder with xdg-user-dirs."_s;
    else if (QFileInfo::exists(dir) && !QFileInfo(dir).isReadable())
      error = u"The desktop folder cannot be read."_s;
    else {
      QMimeDatabase mime;
      auto filters = QDir::AllEntries | QDir::NoDotAndDotDot | QDir::System;
      if (hidden)
        filters |= QDir::Hidden;
      QDirIterator it(dir, filters, QDirIterator::NoIteratorFlags);
      while (it.hasNext() && entries.size() < 2000) {
        it.next();
        const auto info = it.fileInfo();
        const auto type =
            mime.mimeTypeForFile(info, QMimeDatabase::MatchExtension);
        QString name = info.fileName(),
                icon = info.isDir() ? u"folder"_s : type.iconName();
        if (info.suffix() == u"desktop"_s && info.isFile() &&
            !info.isSymLink() && info.isExecutable() &&
            info.ownerId() == getuid() && info.size() <= 1024 * 1024) {
          if (auto *app = g_desktop_app_info_new_from_filename(
                  info.absoluteFilePath().toUtf8().constData())) {
            name =
                QString::fromUtf8(g_app_info_get_display_name(G_APP_INFO(app)));
            if (auto *gicon = g_app_info_get_icon(G_APP_INFO(app));
                gicon && G_IS_THEMED_ICON(gicon)) {
              const auto names = g_themed_icon_get_names(G_THEMED_ICON(gicon));
              if (names && names[0])
                icon = QString::fromUtf8(names[0]);
            }
            g_object_unref(app);
          }
        }
        entries.append(QVariantMap{
            {u"name"_s, name},
            {u"fileName"_s, info.fileName()},
            {u"path"_s, info.absoluteFilePath()},
            {u"url"_s, QUrl::fromLocalFile(info.absoluteFilePath())
                           .toString(QUrl::FullyEncoded)},
            {u"directory"_s, info.isDir()},
            {u"icon"_s, icon},
            {u"size"_s, info.size()},
            {u"modified"_s, info.lastModified().toMSecsSinceEpoch()}});
      }
      if (it.hasNext())
        error =
            u"Only the first 2000 desktop items are shown. Open the folder in your file manager to see everything."_s;
    }
    return QVariantMap{{u"entries"_s, entries}, {u"error"_s, error}};
  }));
}
void DesktopFiles::place(const QString &output, const QString &value,
                         int column, int row) {
  const auto name = QFileInfo(QUrl(value).toLocalFile()).fileName();
  if (!m_active || column < 0 || row < 0 || column > 1000 || row > 1000 ||
      output.size() > 256 ||
      std::none_of(m_entries.cbegin(), m_entries.cend(),
                   [&](const QVariant &entry) {
                     return entry.toMap().value(u"url"_s).toString() == value;
                   }))
    return;
  auto screen = m_positions.value(output).toMap();
  screen.insert(name, QVariantList{column, row});
  m_positions.insert(output, screen);
  const auto path =
      (QStandardPaths::writableLocation(QStandardPaths::ConfigLocation) +
       u"/hics"_s);
  QDir().mkpath(path);
  QSaveFile file(path + u"/desktop-icons.json"_s);
  if (file.open(QIODevice::WriteOnly)) {
    file.setPermissions(QFileDevice::ReadOwner | QFileDevice::WriteOwner);
    file.write(QJsonDocument(QJsonObject::fromVariantMap(m_positions))
                   .toJson(QJsonDocument::Compact));
    file.commit();
  }
  emit changed();
}
void DesktopFiles::tidy() {
  m_positions.clear();
  QFile::remove(
      (QStandardPaths::writableLocation(QStandardPaths::ConfigLocation) +
       u"/hics"_s) +
      u"/desktop-icons.json"_s);
  emit changed();
}
void DesktopFiles::launch(const QString &program, const QStringList &args) {
  auto *p = new QProcess(this);
  p->setProcessEnvironment(hics::util::applicationEnvironment());
  p->setProgram(program);
  p->setArguments(args);
  hics::util::isolateApplication(*p);
  connect(p, &QProcess::errorOccurred, this, [this, p] {
    m_error = p->errorString();
    emit changed();
    p->deleteLater();
  });
  connect(p, qOverload<int, QProcess::ExitStatus>(&QProcess::finished), this,
          [this, p](int code, QProcess::ExitStatus status) {
            if (code || status != QProcess::NormalExit) {
              m_error = QString::fromUtf8(p->readAllStandardError()).left(2048);
              if (m_error.isEmpty())
                m_error = u"The application could not be started."_s;
              emit changed();
            }
            p->deleteLater();
          });
  p->start();
}
void DesktopFiles::open(const QString &value) {
  const QUrl url(value);
  if (value == u"trash:///"_s) {
    launch(u"gio"_s, {u"open"_s, value});
    return;
  }
  if (!url.isLocalFile())
    return;
  const QFileInfo info(url.toLocalFile());
  if (!info.exists())
    return;
  if (info.suffix() == u"desktop"_s) {
    // Never execute a downloaded/copied launcher just because it is visible.
    if (info.isSymLink() || !info.isExecutable() ||
        info.ownerId() != getuid()) {
      m_error =
          u"This launcher is not trusted. Review it and enable launching in your file manager."_s;
      emit changed();
      reveal(value);
      return;
    }
    launch(u"gio"_s, {u"launch"_s, info.absoluteFilePath()});
  } else
    launch(u"gio"_s, {u"open"_s, value});
}
void DesktopFiles::reveal(const QString &value, bool properties) {
  const QUrl url(value);
  if (!url.isLocalFile())
    return;
  auto message = QDBusMessage::createMethodCall(
      u"org.freedesktop.FileManager1"_s, u"/org/freedesktop/FileManager1"_s,
      u"org.freedesktop.FileManager1"_s,
      properties ? u"ShowItemProperties"_s : u"ShowItems"_s);
  message.setArguments({QStringList{value}, QString()});
  auto *w = new QDBusPendingCallWatcher(
      QDBusConnection::sessionBus().asyncCall(message, 5000), this);
  connect(w, &QDBusPendingCallWatcher::finished, this, [this, w, url] {
    QDBusPendingReply<> result = *w;
    w->deleteLater();
    if (result.isError())
      launch(u"gio"_s,
             {u"open"_s,
              QUrl::fromLocalFile(QFileInfo(url.toLocalFile()).absolutePath())
                  .toString()});
  });
}
void DesktopFiles::copy(const QStringList &values, bool cut) {
  if (values.size() > 128) {
    m_error = u"Choose between one and 128 items"_s;
    emit changed();
    return;
  }
  auto *mime = new QMimeData;
  QList<QUrl> urls;
  for (const auto &value : values) {
    QUrl url(value);
    if (url.isLocalFile() && (QFileInfo::exists(url.toLocalFile()) ||
                              QFileInfo(url.toLocalFile()).isSymLink()))
      urls << url;
  }
  if (urls.isEmpty()) {
    delete mime;
    return;
  }
  mime->setUrls(urls);
  QByteArray gnome = cut ? "cut" : "copy";
  for (const auto &url : urls)
    gnome += '\n' + url.toEncoded();
  mime->setData(u"x-special/gnome-copied-files"_s, gnome);
  mime->setData(u"application/x-kde-cutselection"_s,
                cut ? QByteArray("1") : QByteArray("0"));
  QGuiApplication::clipboard()->setMimeData(mime);
}
void DesktopFiles::releaseCut(const QStringList &sources) {
  const auto current = clipboardFiles();
  if (current.value(u"cut"_s).toBool() &&
      current.value(u"sources"_s).toStringList() == sources)
    QGuiApplication::clipboard()->clear();
}
QVariantMap DesktopFiles::clipboardFiles() const {
  const auto *mime = QGuiApplication::clipboard()->mimeData();
  QStringList paths;
  bool cut = false;
  if (!mime)
    return {};
  auto urls = mime->urls();
  if (mime->hasFormat(u"x-special/gnome-copied-files"_s)) {
    const auto data = mime->data(u"x-special/gnome-copied-files"_s).split('\n');
    cut = data.value(0) == "cut";
    if (urls.isEmpty())
      for (int i = 1; i < data.size(); ++i)
        urls << QUrl::fromEncoded(data[i]);
  }
  cut |= mime->data(u"application/x-kde-cutselection"_s) == "1";
  for (const auto &url : urls)
    if (url.isLocalFile())
      paths << url.toLocalFile();
  return {{u"sources"_s, paths}, {u"cut"_s, cut}};
}
} // namespace hyprstack::services
