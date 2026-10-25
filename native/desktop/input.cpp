#include "desktopentry.hpp"
#include "service.hpp"
#include "util/applicationenv.hpp"
#include <QDBusArgument>
#include <QDBusConnection>
#include <QDBusConnectionInterface>
#include <QDBusMessage>
#include <QDBusMetaType>
#include <QDBusVariant>
#include <QDir>
#include <QJsonArray>
#include <QRegularExpression>
#include <QSaveFile>
#include <QSet>
#include <QSettings>
#include <QStandardPaths>
#include <unicode/uchar.h>
struct HicsInputPair {
  QString id, layout;
};
Q_DECLARE_METATYPE(HicsInputPair)
static QDBusArgument &operator<<(QDBusArgument &arg, const HicsInputPair &p) {
  arg.beginStructure();
  arg << p.id << p.layout;
  arg.endStructure();
  return arg;
}
static const QDBusArgument &operator>>(const QDBusArgument &arg,
                                       HicsInputPair &p) {
  arg.beginStructure();
  arg >> p.id >> p.layout;
  arg.endStructure();
  return arg;
}
namespace HicsDesktop {
namespace {
QDBusMessage controller(const QString &method, QVariantList args = {}) {
  auto message = QDBusMessage::createMethodCall(
      "org.fcitx.Fcitx5", "/controller", "org.fcitx.Fcitx.Controller1", method);
  message.setArguments(args);
  auto reply = QDBusConnection::sessionBus().call(message, QDBus::Block, 5000);
  if (reply.type() == QDBusMessage::ErrorMessage)
    throw std::runtime_error(reply.errorMessage().toStdString());
  return reply;
}
QJsonArray methods() {
  QJsonArray out;
  const auto reply = controller("AvailableInputMethods");
  if (reply.arguments().isEmpty())
    return out;
  const auto arg = qvariant_cast<QDBusArgument>(reply.arguments()[0]);
  arg.beginArray();
  while (!arg.atEnd() && out.size() < 4096) {
    QString id, name, nativeName, icon, label, language;
    bool configurable = false;
    arg.beginStructure();
    arg >> id >> name >> nativeName >> icon >> label >> language >>
        configurable;
    arg.endStructure();
    out.append(QJsonObject{{"id", id},
                           {"name", name},
                           {"nativeName", nativeName},
                           {"language", language},
                           {"configurable", configurable}});
  }
  arg.endArray();
  return out;
}
QString groupName(const QJsonObject &args) {
  auto value = args["group"].toString().trimmed();
  if (value.isEmpty() || value.size() > 80 || value.contains(QChar::Null) ||
      value.contains('\n'))
    throw std::runtime_error("Choose a valid input method group name");
  return value;
}
} // namespace
void Service::input(const QSharedPointer<Job> &job) {
  if (job->operation == "input.configure") {
    application(job, "fcitx5-configtool", {});
    return;
  }
  const auto op = job->operation, dir = directory;
  const auto args = job->arguments;
  worker(job, [op, args, dir] {
    auto prefs = readJson(dir + "/input.json");
    if (prefs.isEmpty())
      prefs = {{"recent", QJsonArray{}}, {"favourites", QJsonArray{}}};
    if (op == "input.symbols") {
      QJsonArray rows;
      const auto query = args["query"].toString().trimmed().toUpper().left(100);
      const auto category = args["category"].toString("emoji");
      auto append = [&](char32_t code) {
        if (!QChar::isPrint(code) || QChar::isSpace(code))
          return;
        char name[256];
        UErrorCode status = U_ZERO_ERROR;
        u_charName(code, U_UNICODE_CHAR_NAME, name, sizeof(name), &status);
        if (U_FAILURE(status))
          return;
        QString label = QString::fromLatin1(name),
                symbol = QString::fromUcs4(&code, 1);
        if (!query.isEmpty() && !label.contains(query) &&
            !symbol.contains(query) &&
            query !=
                QString("U+%1").arg(uint(code), 4, 16, QChar('0')).toUpper())
          return;
        rows.append(QJsonObject{
            {"text", symbol},
            {"name", label},
            {"code",
             QString("U+%1").arg(uint(code), 4, 16, QChar('0')).toUpper()}});
      };
      const auto hex =
          QRegularExpression("^(?:U\\+|0X)([0-9A-F]{1,6})$").match(query);
      if (hex.hasMatch()) {
        bool valid = false;
        const uint code = hex.captured(1).toUInt(&valid, 16);
        if (valid && code <= 0x10ffff && !(code >= 0xd800 && code <= 0xdfff))
          append(code);
      } else if (category == "recent" || category == "favourites") {
        for (const auto &value : prefs[category].toArray()) {
          const auto text = value.toString();
          if (!text.isEmpty())
            rows.append(QJsonObject{{"text", text}, {"name", text}});
        }
      } else {
        uint from = 0x1f300, to = 0x1faff;
        if (category == "symbols") {
          from = 0x2000;
          to = 0x2bff;
        } else if (category == "latin") {
          from = 0xa1;
          to = 0x24f;
        } else if (category == "all") {
          from = 0x21;
          to = 0x10ffff;
        }
        for (uint code = from; code <= to && rows.size() < 120; ++code)
          append(code);
      }
      return QJsonObject{{"items", rows}, {"preferences", prefs}};
    }
    if (op == "input.copy" || op == "input.favourite") {
      const auto text = args["text"].toString();
      if (text.isEmpty() || text.toUtf8().size() > 128 ||
          text.contains(QChar::Null))
        return QJsonObject{{"error", "Choose a character or emoji"}};
      const auto key =
          op == "input.copy" ? QString("recent") : QString("favourites");
      auto list = prefs[key].toArray();
      for (int i = list.size() - 1; i >= 0; --i)
        if (list[i].toString() == text)
          list.removeAt(i);
      if (op == "input.copy" || args["enabled"].toBool())
        list.prepend(text);
      while (list.size() > 40)
        list.removeLast();
      prefs[key] = list;
      writeJson(dir + "/input.json", prefs);
      if (op == "input.copy") {
        QProcess copy;
        copy.setProcessEnvironment(hics::util::applicationEnvironment());
        copy.start("wl-copy", {"--type", "text/plain;charset=utf-8"});
        if (!copy.waitForStarted(3000))
          return QJsonObject{{"error", copy.errorString()}};
        copy.write(text.toUtf8());
        copy.closeWriteChannel();
        if (!copy.waitForFinished(5000)) {
          copy.kill();
          copy.waitForFinished();
          return QJsonObject{{"error", "Clipboard owner did not respond"}};
        }
        if (copy.exitCode() != 0)
          return QJsonObject{{"error", "Cannot copy this character"}};
      }
      return QJsonObject{{"ok", true}, {"preferences", prefs}};
    }
    if (op == "input.osk") {
      const auto running =
          QDBusConnection::sessionBus().interface()->isServiceRegistered(
              "sm.puri.OSK0");
      if (args["visible"].toBool() &&
          (!running.isValid() || !running.value())) {
        const auto start =
            command("systemctl", {"--user", "start", "mobi.phosh.OSK.service"},
                    10000, 16384);
        if (start.exitCode != 0)
          return QJsonObject{
              {"error", "Cannot start the on-screen keyboard; verify "
                        "Squeekboard and the Wayland input-method protocol"}};
      }

      auto call = QDBusMessage::createMethodCall(
          "sm.puri.OSK0", "/sm/puri/OSK0", "sm.puri.OSK0", "SetVisible");
      call.setArguments({args["visible"].toBool()});
      auto reply = QDBusConnection::sessionBus().call(call, QDBus::Block, 5000);
      if (reply.type() == QDBusMessage::ErrorMessage)
        return QJsonObject{{"error", reply.errorMessage()}};
      return QJsonObject{{"ok", true}};
    }
    if (op == "input.enable") {
      const auto reply =
          QDBusConnection::sessionBus().interface()->startService(
              "org.fcitx.Fcitx5");
      return reply.isValid() ? QJsonObject{{"ok", true}}
                             : QJsonObject{{"error", reply.error().message()}};
    }
    if (op == "input.preferences") {
      const auto path =
          QStandardPaths::writableLocation(QStandardPaths::ConfigLocation) +
          "/autostart/org.fcitx.Fcitx5.desktop";
      if (QFileInfo(path).isSymLink())
        return QJsonObject{
            {"error", "The input method autostart entry is a symbolic link; "
                      "edit it through its owner"}};
      QByteArray content(
          "[Desktop Entry]\nType=Application\nName=Fcitx 5\nExec=fcitx5 -d\n");
      if (QFileInfo::exists(path)) {
        QFile file(path);
        if (!file.open(QIODevice::ReadOnly) || file.size() > 1024 * 1024)
          return QJsonObject{
              {"error",
               "Cannot read the existing input method autostart entry"}};
        content = file.readAll();
      }
      saveAutostart(path, content, !args["startAtLogin"].toBool());
      return QJsonObject{{"ok", true}};
    }
    if (op == "input.status") {
      const auto running =
          QDBusConnection::sessionBus().interface()->isServiceRegistered(
              "org.fcitx.Fcitx5");
      QJsonObject out{
          {"running", running.isValid() && running.value()},
          {"preferences", prefs},
          {"oskAvailable",
           !QStandardPaths::findExecutable("squeekboard").isEmpty()}};
      const auto user =
          QStandardPaths::writableLocation(QStandardPaths::ConfigLocation) +
          "/autostart/org.fcitx.Fcitx5.desktop";
      const auto autostart =
          QFileInfo::exists(user)
              ? user
              : QString("/etc/xdg/autostart/org.fcitx.Fcitx5.desktop");
      QSettings login(autostart, QSettings::IniFormat);
      out["startAtLogin"] =
          QFileInfo::exists(autostart) &&
          !login.value("Desktop Entry/Hidden", false).toBool();
      if (!out["running"].toBool())
        return out;
      out["methods"] = methods();
      const auto groups = controller("InputMethodGroups");
      out["groups"] = QJsonArray::fromStringList(
          groups.arguments().value(0).toStringList());
      out["currentGroup"] =
          controller("CurrentInputMethodGroup").arguments().value(0).toString();
      out["currentMethod"] =
          controller("CurrentInputMethod").arguments().value(0).toString();
      const auto group = args["group"].toString(out["currentGroup"].toString());
      const auto info = controller("InputMethodGroupInfo", {group});
      out["group"] = group;
      out["layout"] = info.arguments().value(0).toString();
      QJsonArray entries;
      if (info.arguments().size() > 1) {
        const auto arg = qvariant_cast<QDBusArgument>(info.arguments()[1]);
        arg.beginArray();
        while (!arg.atEnd()) {
          QString id, layout;
          arg.beginStructure();
          arg >> id >> layout;
          arg.endStructure();
          entries.append(QJsonObject{{"id", id}, {"layout", layout}});
        }
        arg.endArray();
      }
      out["entries"] = entries;
      return out;
    }
    if (op == "input.method-select") {
      const auto id = args["id"].toString();
      bool found = false;
      for (const auto &row : methods())
        if (row.toObject()["id"].toString() == id)
          found = true;
      if (!found)
        return QJsonObject{{"error", "Input method is not installed"}};
      controller("SetCurrentIM", {id});
      return QJsonObject{{"ok", true}};
    }
    if (op.startsWith("input.group-")) {
      const auto group = groupName(args);
      if (op == "input.group-create")
        controller("AddInputMethodGroup", {group});
      else if (op == "input.group-remove") {
        const auto groups =
            controller("InputMethodGroups").arguments().value(0).toStringList();
        if (groups.size() <= 1)
          return QJsonObject{{"error", "Keep at least one input method group"}};
        controller("RemoveInputMethodGroup", {group});
      } else if (op == "input.group-activate")
        controller("SwitchInputMethodGroup", {group});
      else if (op == "input.group-save") {
        const auto rows = args["entries"].toArray();
        if (rows.isEmpty() || rows.size() > 64)
          return QJsonObject{
              {"error", "Choose between one and 64 input methods"}};
        QSet<QString> installed;
        for (const auto &row : methods())
          installed.insert(row.toObject()["id"].toString());
        QList<HicsInputPair> entries;
        for (const auto &row : rows) {
          auto object = row.toObject();
          const auto id = object["id"].toString(),
                     layout = object["layout"].toString();
          if (!installed.contains(id) || layout.size() > 128)
            return QJsonObject{
                {"error", "Unknown input method or invalid layout"}};
          entries.append({id, layout});
        }
        qDBusRegisterMetaType<HicsInputPair>();
        qDBusRegisterMetaType<QList<HicsInputPair>>();
        controller("SetInputMethodGroupInfo",
                   {group, args["layout"].toString().left(128),
                    QVariant::fromValue(entries)});
      } else
        return QJsonObject{{"error", "Unknown input group operation"}};
      return QJsonObject{{"ok", true}};
    }
    return QJsonObject{{"error", "Unknown text input operation"}};
  });
}
} // namespace HicsDesktop
