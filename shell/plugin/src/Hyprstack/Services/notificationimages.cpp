#include "notificationimages.hpp"
#include <QBuffer>
#include <QCryptographicHash>
#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QFutureWatcher>
#include <QImageIOHandler>
#include <QImageReader>
#include <QPixmap>
#include <QQmlEngine>
#include <QQuickImageProvider>
#include <QQuickTextureFactory>
#include <QSaveFile>
#include <QStandardPaths>
#include <QUrl>
#include <QtConcurrent>
using namespace Qt::StringLiterals;
namespace hyprstack::services {
NotificationImages::NotificationImages(QObject *p) : QObject(p) {
  m_pool.setMaxThreadCount(1);
  m_pool.setExpiryTimeout(1000);
}
NotificationImages::~NotificationImages() {
  m_pool.clear();
  m_pool.waitForDone();
}
void NotificationImages::cache(const QString &source, bool original,
                               QJSValue callback) {
  if (m_pending >= 32) {
    if (callback.isCallable())
      callback.call({QString()});
    return;
  }
  QImage image;
  QString path;
  const QUrl url(source);
  if (url.scheme() == u"image"_s) {
    auto *engine = qmlEngine(this);
    auto *provider = engine ? dynamic_cast<QQuickImageProvider *>(
                                  engine->imageProvider(url.host()))
                            : nullptr;
    if (provider) {
      QSize size;
      const QString id = url.path().mid(1) +
                         (url.hasQuery() ? u"?"_s + url.query() : QString());
      if (provider->imageType() == QQmlImageProviderBase::Image)
        image = provider->requestImage(id, &size, QSize());
      else if (provider->imageType() == QQmlImageProviderBase::Pixmap)
        image = provider->requestPixmap(id, &size, QSize()).toImage();
      else if (provider->imageType() == QQmlImageProviderBase::Texture) {
        auto *factory = provider->requestTexture(id, &size, QSize());
        if (factory) {
          image = factory->image();
          delete factory;
        }
      }
    }
  } else if (url.isLocalFile())
    path = url.toLocalFile();
  else if (url.scheme().isEmpty() && QDir::isAbsolutePath(source))
    path = source;
  if (image.isNull() && path.isEmpty()) {
    if (callback.isCallable())
      callback.call({QString()});
    return;
  }
  const qint64 memory = image.sizeInBytes();
  if (memory > 64 * 1024 * 1024 || m_pendingBytes + memory > 64 * 1024 * 1024) {
    if (callback.isCallable())
      callback.call({QString()});
    return;
  }
  ++m_pending;
  m_pendingBytes += memory;
  auto *watcher = new QFutureWatcher<QString>(this);
  connect(watcher, &QFutureWatcher<QString>::finished, this,
          [this, watcher, callback, memory]() mutable {
            --m_pending;
            m_pendingBytes -= memory;
            const auto result = watcher->result();
            watcher->deleteLater();
            if (callback.isCallable())
              callback.call({result});
          });
  // Use the shell's stable XDG cache path, independent of the application name.
  const QString root =
      qEnvironmentVariable("XDG_CACHE_HOME", QDir::homePath() + u"/.cache"_s) +
      u"/hics/imagecache/notifs"_s;
  watcher->setFuture(QtConcurrent::run(
      &m_pool, [image, path, original, root]() mutable -> QString {
        QByteArray bytes;
        if (!path.isEmpty()) {
          QFile file(path);
          QFileInfo info(file);
          if (!info.isFile() || info.size() > 64 * 1024 * 1024 ||
              !file.open(QIODevice::ReadOnly))
            return {};
          if (original) {
            bytes = file.read(64 * 1024 * 1024 + 1);
            if (bytes.size() > 64 * 1024 * 1024)
              return {};
          }
          QImageReader reader(path);
          reader.setAutoTransform(true);
          const QSize size = reader.size();
          if (!size.isValid() ||
              qint64(size.width()) * size.height() > 64 * 1024 * 1024)
            return {};
          if (!original &&
              !reader.supportsOption(QImageIOHandler::ScaledSize) &&
              qint64(size.width()) * size.height() > 16 * 1024 * 1024)
            return {};
          if (!original) {
            reader.setScaledSize(size.scaled(1280, 1280, Qt::KeepAspectRatio));
            image = reader.read();
          }
        }
        if (bytes.isEmpty() && image.isNull())
          return {};
        if (!original || path.isEmpty()) {
          if (image.isNull())
            return {};
          if (image.width() > 1280 || image.height() > 1280)
            image = image.scaled(1280, 1280, Qt::KeepAspectRatio,
                                 Qt::SmoothTransformation);
          bytes.clear();
          QBuffer buffer(&bytes);
          buffer.open(QIODevice::WriteOnly);
          if (!image.save(&buffer, "PNG"))
            return {};
        }
        const auto hash =
            QCryptographicHash::hash(bytes, QCryptographicHash::Sha256).toHex();
        QString suffix = u"png"_s;
        if (original && !path.isEmpty()) {
          QImageReader reader(path);
          suffix = QString::fromLatin1(reader.format());
          if (suffix != u"png"_s && suffix != u"jpeg"_s && suffix != u"jpg"_s &&
              suffix != u"webp"_s)
            return {};
        }
        QDir().mkpath(root);
        QFile::setPermissions(root, QFileDevice::ReadOwner |
                                        QFileDevice::WriteOwner |
                                        QFileDevice::ExeOwner);
        const QString target =
            root + u"/"_s + QString::fromLatin1(hash) + u"."_s + suffix;
        if (!QFileInfo::exists(target)) {
          QSaveFile file(target);
          file.setPermissions(QFileDevice::ReadOwner | QFileDevice::WriteOwner);
          if (!file.open(QIODevice::WriteOnly) ||
              file.write(bytes) != bytes.size() || !file.commit())
            return {};
        }
        return target;
      }));
}
} // namespace hyprstack::services
