#pragma once

#include <qjsengine.h>
#include <qobject.h>
#include <qqmlengine.h>
#include <qqmlintegration.h>
#include <qurl.h>
#include <QFileSystemWatcher>
#include <QTimer>

namespace hyprstack::images {

class IUtils : public QObject {
    Q_OBJECT
    QML_ELEMENT
    QML_SINGLETON
    Q_PROPERTY(QUrl profilePicture READ profilePicture NOTIFY profilePictureChanged)

public:
    static IUtils* create(QQmlEngine* engine, QJSEngine* jsEngine);

    Q_INVOKABLE static QUrl urlForPath(const QString& path, int fillMode);
    QUrl profilePicture();
signals:
    void profilePictureChanged();

private:
    explicit IUtils(QObject* parent = nullptr);
    void refreshProfilePicture(bool notify);
    QFileSystemWatcher *m_profileWatcher = nullptr;
    QTimer *m_profileTimer = nullptr;
    QString m_profilePath, m_profileFingerprint;
    QUrl m_profilePicture;
    quint64 m_profileRevision = 0;
    bool m_profileForceReload = false;
};

} // namespace hyprstack::images
