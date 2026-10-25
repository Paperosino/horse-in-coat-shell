#include "service.hpp"
#include "util/applicationenv.hpp"
#include <QDBusConnection>
#include <QDBusMessage>
#include <QDBusPendingCall>
#include <QDateTime>
#include <QProcessEnvironment>
#include <QTimer>
namespace HicsDesktop {
void Service::initComfort() {
  comfortState = readJson(directory + "/comfort.json");
  comfortDeadline.setSingleShot(true);
  connect(&comfortDeadline, &QTimer::timeout, this, &Service::updateComfort);
  QTimer::singleShot(0, this, &Service::updateComfort);
}
void Service::updateComfort() {
  const auto now = QDateTime::currentMSecsSinceEpoch();
  auto focus = comfortState["focus"].toObject();
  const auto deadline = focus["deadline"].toInteger();
  bool changed = false;
  if (deadline > 0 && deadline <= now) {
    const bool work = focus["phase"].toString() == "work";
    const int completed = focus["completed"].toInt() + (work ? 1 : 0);
    focus["completed"] = completed;
    focus["phase"] = work ? "break" : "ready";
    // Never consume a break while the service was stopped or the machine slept.
    const auto seconds =
        completed % qBound(1, focus["rounds"].toInt(4), 12) == 0
            ? focus["longBreakSeconds"].toInt(900)
            : focus["breakSeconds"].toInt(300);
    focus["deadline"] = work ? now + qint64(seconds) * 1000 : 0;
    focus["remainingSeconds"] = work ? seconds : 0;
    comfortState["focus"] = focus;
    changed = true;
    const bool ru =
        qEnvironmentVariable("LC_MESSAGES", qEnvironmentVariable("LANG"))
            .startsWith("ru");
    auto message = QDBusMessage::createMethodCall(
        "org.freedesktop.Notifications", "/org/freedesktop/Notifications",
        "org.freedesktop.Notifications", "Notify");
    message.setArguments(
        {QString("hics"), uint(0), QString("alarm"),
         ru ? QString(work ? "Пора сделать перерыв" : "Перерыв окончен")
            : QString(work ? "Time for a break" : "Break finished"),
         ru ? QString("Откройте таймер концентрации, когда будете готовы "
                      "продолжить.")
            : QString("Open the focus timer when you are ready to continue."),
         QStringList{}, QVariantMap{{"x-hics-focus", true}}, int(-1)});
    QDBusConnection::sessionBus().asyncCall(message, 5000);
  }
  const auto awake = comfortState["awakeDeadline"].toInteger();
  if (awake && awake <= now) {
    comfortState["awakeDeadline"] = 0;
    changed = true;
  }
  qint64 next = 0;
  for (const auto value :
       {comfortState["focus"].toObject()["deadline"].toInteger(),
        comfortState["awakeDeadline"].toInteger()})
    if (value > now && (!next || value < next))
      next = value;
  comfortDeadline.stop();
  if (next)
    comfortDeadline.start(int(qMin<qint64>(next - now, 86400000)));
  if (changed) {
    try {
      writeJson(directory + "/comfort.json", comfortState);
    } catch (const std::exception &) {
      comfortState["storageError"] = "Cannot save timer state";
    }
    publish();
  }
}
void Service::comfort(const QSharedPointer<Job> &job) {
  const auto op = job->operation;
  const auto args = job->arguments;
  auto focus = comfortState["focus"].toObject();
  const auto now = QDateTime::currentMSecsSinceEpoch();
  if (op == "comfort.plain-text") {
    worker(job, [] {
      const auto value =
          command("wl-paste", {"--no-newline", "--type", "text/plain"}, 3000,
                  1024 * 1024);
      if (value.exitCode || value.output.isEmpty() ||
          value.output.size() >= 1024 * 1024)
        return QJsonObject{
            {"error", "The clipboard must contain text smaller than 1 MiB"}};
      QProcess copy;
      copy.setProcessEnvironment(hics::util::applicationEnvironment());
      copy.start("wl-copy",
                 {"--sensitive", "--type", "text/plain;charset=utf-8"});
      if (!copy.waitForStarted(3000))
        return QJsonObject{{"error", "Cannot access the Wayland clipboard"}};
      copy.write(value.output);
      copy.closeWriteChannel();
      if (!copy.waitForFinished(3000) || copy.exitCode()) {
        copy.kill();
        copy.waitForFinished(1000);
        return QJsonObject{{"error", "Cannot copy plain text"}};
      }
      return QJsonObject{{"ok", true}};
    });
    return;
  }
  if (op == "comfort.focus-start") {
    if (focus["deadline"].toInteger() > now || focus["paused"].toBool()) {
      finish(job, {}, "Stop the current focus session first");
      return;
    }
    const int seconds = qBound(1, args["minutes"].toInt(25), 240) * 60;
    focus = QJsonObject{
        {"phase", "work"},
        {"deadline", now + qint64(seconds) * 1000},
        {"remainingSeconds", seconds},
        {"breakSeconds", qBound(1, args["breakMinutes"].toInt(5), 60) * 60},
        {"longBreakSeconds",
         qBound(1, args["longBreakMinutes"].toInt(15), 120) * 60},
        {"rounds", qBound(1, args["rounds"].toInt(4), 12)},
        {"completed", focus["completed"].toInt()},
        {"quiet", args["quiet"].toBool(true)},
        {"keepAwake", args["keepAwake"].toBool(false)}};
  } else if (op == "comfort.focus-pause") {
    if (focus["deadline"].toInteger() <= now) {
      finish(job, {}, "No running timer to pause");
      return;
    }
    focus["remainingSeconds"] =
        (focus["deadline"].toInteger() - now + 999) / 1000;
    focus["deadline"] = 0;
    focus["paused"] = true;
  } else if (op == "comfort.focus-resume") {
    if (!focus["paused"].toBool()) {
      finish(job, {}, "No paused timer to resume");
      return;
    }
    focus["deadline"] = now + qint64(focus["remainingSeconds"].toInt()) * 1000;
    focus["paused"] = false;
  } else if (op == "comfort.focus-options") {
    if (args.contains("quiet"))
      focus["quiet"] = args["quiet"].toBool();
    if (args.contains("keepAwake"))
      focus["keepAwake"] = args["keepAwake"].toBool();
  } else if (op == "comfort.focus-stop") {
    focus = QJsonObject{{"phase", "idle"}, {"deadline", 0}};
  } else if (op == "comfort.awake") {
    const auto minutes = args["minutes"].toInt();
    if (minutes < 0 || minutes > 1440) {
      finish(job, {}, "Choose between 0 and 1440 minutes");
      return;
    }
    comfortState["awakeDeadline"] = minutes ? now + qint64(minutes) * 60000 : 0;
  } else if (op != "comfort.status") {
    finish(job, {}, "Unknown comfort operation");
    return;
  }
  if (op != "comfort.status") {
    comfortState["focus"] = focus;
    writeJson(directory + "/comfort.json", comfortState);
    updateComfort();
    publish();
  }
  finish(job, comfortState);
}
} // namespace HicsDesktop
