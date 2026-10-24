#pragma once
#include <QNetworkReply>
#include <QSharedPointer>
#include <QTimer>

namespace hics {
// Drain incrementally: setReadBufferSize alone merely stops reading the socket.
// The application buffer, including decompressed HTTP data, also needs a cap.
inline void boundNetworkReply(QNetworkReply* reply, qsizetype limit = 4 * 1024 * 1024) {
    auto body = QSharedPointer<QByteArray>::create();
    reply->setReadBufferSize(64 * 1024);
    auto drain = [reply, body, limit] {
        while (reply->bytesAvailable() > 0) {
            const auto chunk = reply->read(qMin<qsizetype>(64 * 1024, limit - body->size() + 1));
            if (chunk.isEmpty()) break;
            if (body->size() + chunk.size() > limit) {
                reply->setProperty("hicsResponseTooLarge", true);
                body->clear();
                reply->abort();
                return;
            }
            body->append(chunk);
        }
    };
    QObject::connect(reply, &QIODevice::readyRead, reply, drain);
    QObject::connect(reply, &QNetworkReply::finished, reply, [reply, body, drain] {
        if (!reply->property("hicsResponseTooLarge").toBool()) drain();
        reply->setProperty("hicsResponseBody", *body);
    });
    // A transfer timeout only bounds inactivity; also bound total request time.
    QTimer::singleShot(30000, reply, [reply] { if (!reply->isFinished()) reply->abort(); });
}
inline QByteArray networkBody(QNetworkReply* reply) {
    return reply->property("hicsResponseBody").toByteArray();
}
}
