#include "backend.hpp"
#include <QJsonDocument>
#include <QJsonArray>
#include <QMutex>
#include <QMutexLocker>
#include <QProcess>
#include <QRegularExpression>
#include <QFileInfo>
#include <QDir>

namespace System {
void validateAppearance(const QString &op, const QJsonObject &o) {
    const QStringList fields{"colours", "mode", "antialias", "hinting", "icons", "cursor", "cursorSize", "font", "qtFont", "controls"};
    if (op != "configure" || o.size() != fields.size()) throw Failure("invalid", "Invalid appearance request");
    for (const auto &key : fields) if (!o.contains(key)) throw Failure("invalid", "Missing appearance field");
    const auto colours = o.value("colours").toObject();
    for (const auto &role : {"surface", "onSurface", "surfaceContainer", "primary", "onPrimary", "outlineVariant"})
        if (!colours.contains(role)) throw Failure("invalid", "Missing palette colour");
    if (colours.size() > 256) throw Failure("invalid", "Palette is too large");
    for (auto it = colours.begin(); it != colours.end(); ++it)
        if (!QRegularExpression("^[A-Za-z][A-Za-z0-9_]{0,95}$").match(it.key()).hasMatch() ||
            !it.value().isString() || !QRegularExpression("^[0-9a-fA-F]{6}$").match(it.value().toString()).hasMatch())
            throw Failure("invalid", "Invalid palette colour");
    if (!QStringList{"dark", "light"}.contains(o["mode"].toString()) || !o["antialias"].isBool() ||
        !QStringList{"none", "slight", "medium", "full"}.contains(o["hinting"].toString()))
        throw Failure("invalid", "Invalid appearance preference");
    const auto size = o["cursorSize"];
    if (!size.isDouble() || size.toDouble() != size.toInt() || size.toInt() < 8 || size.toInt() > 128)
        throw Failure("invalid", "Invalid cursor size");
    for (const auto &key : {"icons", "cursor"})
        if (!o[key].isString() || !QRegularExpression("^[A-Za-z0-9][A-Za-z0-9_. -]{0,127}$").match(o[key].toString()).hasMatch())
            throw Failure("invalid", "Invalid theme name");
    for (const auto &key : {"font", "qtFont"})
        if (!o[key].isString() || o[key].toString().isEmpty() || o[key].toString().size() > 256 ||
            o[key].toString().contains(QRegularExpression("[\\x00-\\x1f]")))
            throw Failure("invalid", "Invalid font");
    const auto controls = o["controls"].toObject();
    if (controls.size() != 2 || !QStringList{"left", "right"}.contains(controls["side"].toString()) || !controls["order"].isArray())
        throw Failure("invalid", "Invalid window controls");
    QStringList order;
    for (const auto &button : controls["order"].toArray()) {
        if (!button.isString() || !QStringList{"minimize", "maximize", "close"}.contains(button.toString()) || order.contains(button.toString()))
            throw Failure("invalid", "Invalid window button order");
        order.append(button.toString());
    }
}
void applyAppearance(const QJsonObject &o) {
    static QMutex lock;
    QMutexLocker guard(&lock);
    QFileInfo source(QStringLiteral(HICS_ROOT_APPEARANCE));
    for (;;) {
        if (!source.exists() || source.ownerId() != 0 ||
            (source.permissions() & (QFile::WriteGroup | QFile::WriteOther)))
            throw Failure("denied", "Root appearance helper must be installed in a root-owned system directory");
        if (source.absoluteFilePath() == "/") break;
        source.setFile(source.absolutePath());
    }
    QProcess worker;
    worker.start("/usr/bin/python3", {"-I", HICS_ROOT_APPEARANCE});
    if (!worker.waitForStarted(3000)) throw Failure("failed", "Cannot start root appearance writer");
    worker.write(QJsonDocument(o).toJson(QJsonDocument::Compact));
    worker.closeWriteChannel();
    if (!worker.waitForFinished(10000)) {
        worker.kill(); worker.waitForFinished(1000);
        throw Failure("failed", "Root appearance writer timed out");
    }
    if (worker.exitStatus() != QProcess::NormalExit || worker.exitCode())
        throw Failure("failed", QString::fromUtf8(worker.readAllStandardError()).left(2048));
}
} // namespace System
