#include "iutils.hpp"

#include "cachingimageprovider.hpp"
#include <QDir>
#include <QFileInfo>
#include <QDateTime>
#include <QUrlQuery>

namespace hyprstack::images {

using Qt::StringLiterals::operator""_s;

IUtils::IUtils(QObject* parent)
    : QObject(parent) {}

IUtils* IUtils::create(QQmlEngine* engine, QJSEngine* jsEngine) {
    Q_UNUSED(jsEngine);

    engine->addImageProvider(u"ccache"_s, new CachingImageProvider(CachingImageProvider::FillMode::Crop));
    engine->addImageProvider(u"fcache"_s, new CachingImageProvider(CachingImageProvider::FillMode::Fit));
    engine->addImageProvider(u"scache"_s, new CachingImageProvider(CachingImageProvider::FillMode::Stretch));

    return new IUtils(engine);
}

QUrl IUtils::profilePicture() {
    if (!m_profileWatcher) {
        m_profilePath = QDir::home().filePath(u".face"_s);
        m_profileWatcher = new QFileSystemWatcher(this);
        m_profileTimer = new QTimer(this);
        m_profileTimer->setSingleShot(true);
        m_profileTimer->setInterval(50);
        const auto schedule = [this] {
            // Coalesce bursts without postponing an update indefinitely.
            if (!m_profileTimer->isActive()) m_profileTimer->start();
        };
        connect(m_profileWatcher, &QFileSystemWatcher::directoryChanged, this, schedule);
        connect(m_profileWatcher, &QFileSystemWatcher::fileChanged, this, [this, schedule] {
            m_profileForceReload = true; schedule();
        });
        connect(m_profileTimer, &QTimer::timeout, this, [this] { refreshProfilePicture(true); });
        m_profileWatcher->addPath(QDir::homePath());
        refreshProfilePicture(false);
    }
    return m_profilePicture;
}

void IUtils::refreshProfilePicture(bool notify) {
    const QFileInfo info(m_profilePath);
    // Absence is normal. Never send a FIFO, directory or broken link to an
    // image decoder just to obtain the fallback icon.
    const bool available = info.isFile() && info.isReadable();
    if (available && !m_profileWatcher->files().contains(m_profilePath))
        m_profileWatcher->addPath(m_profilePath);
    else if (!available && m_profileWatcher->files().contains(m_profilePath))
        m_profileWatcher->removePath(m_profilePath);
    const QString fingerprint = available ? info.canonicalFilePath() + u'\n' + QString::number(info.size()) + u'\n' +
        QString::number(info.lastModified().toMSecsSinceEpoch()) + u'\n' + QString::number(info.birthTime().toMSecsSinceEpoch()) : QString();
    if (!m_profileForceReload && fingerprint == m_profileFingerprint) return;
    m_profileForceReload = false;
    m_profileFingerprint = fingerprint;
    ++m_profileRevision;
    m_profilePicture = available ? urlForPath(m_profilePath, 2) : QUrl();
    if (available) {
        QUrlQuery query;
        query.addQueryItem(u"hics-avatar-revision"_s, QString::number(m_profileRevision));
        m_profilePicture.setQuery(query);
    }
    if (notify) emit profilePictureChanged();
}

QUrl IUtils::urlForPath(const QString& path, int fillMode) {
    if (path.isEmpty())
        return {};

    QString prefix;
    switch (fillMode) {
    case 1: // Image.PreserveAspectFit
        prefix = u"fcache"_s;
        break;
    case 2: // Image.PreserveAspectCrop
        prefix = u"ccache"_s;
        break;
    default: // Image.Stretch or any other ones
        prefix = u"scache"_s;
        break;
    }

    QUrl url;
    url.setScheme(u"image"_s);
    url.setHost(prefix);
    url.setPath(path.startsWith(u'/') ? path : u'/' + path);
    return url;
}

} // namespace hyprstack::images
