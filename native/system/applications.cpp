#include "backend.hpp"
#include "apparmorcontrols.hpp"
#include <QCryptographicHash>
#include <QDateTime>
#include <QDir>
#include <QElapsedTimer>
#include <QFile>
#include <QFileInfo>
#include <QJsonArray>
#include <QJsonDocument>
#include <QMutex>
#include <QMutexLocker>
#include <QProcess>
#include <QRegularExpression>
#include <QSaveFile>
#include <QScopeGuard>
#include <QStandardPaths>
#include <QTemporaryFile>
#include <QUuid>
#ifndef HYPRSTACK_APPARMOR_PARSER
#define HYPRSTACK_APPARMOR_PARSER ""
#endif
#ifndef HYPRSTACK_PACMAN
#define HYPRSTACK_PACMAN ""
#endif
#ifndef HYPRSTACK_AA_ENFORCE
#define HYPRSTACK_AA_ENFORCE ""
#endif
#ifndef HYPRSTACK_AA_COMPLAIN
#define HYPRSTACK_AA_COMPLAIN ""
#endif
#ifndef HYPRSTACK_AA_DISABLE
#define HYPRSTACK_AA_DISABLE ""
#endif
#ifndef HYPRSTACK_SYSTEMD_RUN
#define HYPRSTACK_SYSTEMD_RUN ""
#endif
namespace System {
namespace {
QString run(const QString &program, const QStringList &args,
            int timeout = 15000) {
  if (program.isEmpty())
    throw Failure("unavailable", "Required system tool is not installed");
  QProcess process;
  process.start(program, args);
  if (!process.waitForStarted(5000))
    throw Failure("unavailable", process.errorString());
  QByteArray output;
  QElapsedTimer clock;
  clock.start();
  while (process.state() != QProcess::NotRunning && clock.elapsed() < timeout) {
    process.waitForReadyRead(100);
    output += process.readAllStandardOutput();
    output += process.readAllStandardError();
    if (output.size() > 65536)
      output = output.right(65536);
  }
  if (process.state() != QProcess::NotRunning) {
    process.kill();
    process.waitForFinished();
    throw Failure(
        "timeout",
        "System operation timed out; inspect its systemd job before retrying");
  }
  output += process.readAllStandardOutput();
  output += process.readAllStandardError();
  if (process.exitStatus() != QProcess::NormalExit || process.exitCode() != 0)
    throw Failure(
        "failed",
        output.trimmed().isEmpty()
            ? QString("System operation failed (%1)").arg(process.exitCode())
            : QString::fromUtf8(output.right(8192)).trimmed());
  return QString::fromUtf8(output.right(65536)).trimmed();
}
QString profileFile(const QJsonObject &options) {
  const auto profile = options["profile"].toString();
  if (!QRegularExpression("^[A-Za-z0-9][A-Za-z0-9_.+-]{0,199}$")
           .match(profile)
           .hasMatch())
    throw Failure("invalid", "Choose an AppArmor profile file");
  const QString path = "/etc/apparmor.d/" + profile;
  const QFileInfo info(path);
  if (!info.isFile() || info.isSymLink() || info.ownerId() != 0 ||
      !info.canonicalFilePath().startsWith("/etc/apparmor.d/"))
    throw Failure(
        "invalid",
        "AppArmor profile must be an existing root-owned policy file");
  return path;
}
QString packageFor(const QJsonObject &options) {
  const auto desktop = options["desktop"].toString();
  if (!QRegularExpression("^[A-Za-z0-9][A-Za-z0-9_.+-]{0,240}\\.desktop$")
           .match(desktop)
           .hasMatch())
    throw Failure("invalid", "Invalid application desktop identifier");
  const auto path =
      QFileInfo("/usr/share/applications/" + desktop).canonicalFilePath();
  if (path.isEmpty() || !path.startsWith("/usr/share/applications/") ||
      QFileInfo(path).ownerId() != 0)
    throw Failure(
        "invalid",
        "Only an application owned by a system package can be removed here");
  const auto package = run(HYPRSTACK_PACMAN, {"-Qoq", "--", path});
  if (!QRegularExpression("^[A-Za-z0-9@][A-Za-z0-9@._+:-]{0,199}$")
           .match(package)
           .hasMatch())
    throw Failure("invalid", "Could not identify a single owning package");
  const QStringList protectedPackages = {
      "hic-shell",    "hics-shell", "hyprland",     "quickshell",
      "pacman",       "systemd",    "systemd-libs", "glibc",
      "glib2",        "dbus",       "dbus-broker",  "polkit",
      "sudo",         "pam",        "pambase",      "networkmanager",
      "libnm",        "mesa",       "qt6-base",     "qt6-declarative",
      "gnome-keyring"};
  if (protectedPackages.contains(package) || package == "linux" ||
      package.startsWith("linux-"))
    throw Failure("denied",
                  "This package is required by the system or desktop; use the "
                  "distribution's package tools to manage it");
  const auto installed =
      run(HYPRSTACK_PACMAN, {"-Q", "--", package}).section(' ', 1);
  if (options["version"].toString().isEmpty() ||
      installed != options["version"].toString())
    throw Failure("changed", "The application version changed; refresh its "
                             "information before removing it");
  return package;
}
void rootTask(const QString &executable, const QStringList &arguments,
              const QString &label) {
  const auto unit = "hics-admin-" + QUuid::createUuid().toString(QUuid::Id128);
  QStringList args{"--quiet",
                   "--wait",
                   "--pipe",
                   "--collect",
                   "--expand-environment=no",
                   "--unit=" + unit,
                   "--description=" + label,
                   "--property=Type=exec",
                   "--property=Nice=10",
                   "--property=IOSchedulingClass=idle",
                   "--property=TimeoutStartSec=15min",
                   executable};
  args << arguments;
  run(HYPRSTACK_SYSTEMD_RUN, args, 910000);
}
} // namespace
QJsonObject applicationsStatus() {
  QJsonArray profiles;
  QFile current("/sys/kernel/security/apparmor/profiles");
  const bool active = current.open(QIODevice::ReadOnly);
  if (active) {
    const auto raw = current.read(1024 * 1024);
    for (const auto &line :
         QString::fromUtf8(raw).split('\n', Qt::SkipEmptyParts))
      profiles.append(line);
  }
  QJsonArray files;
  for (const auto &file :
       QDir("/etc/apparmor.d").entryInfoList(QDir::Files | QDir::NoSymLinks))
    if (file.ownerId() == 0 && !file.fileName().startsWith('.'))
      files.append(file.fileName());
  bool serviceEnabled = false;
  QString serviceState;
  try {
    serviceState =
        run(HYPRSTACK_SYSTEMCTL,
            {"show", "apparmor.service", "--property=ActiveState", "--value"},
            5000);
    const auto enabled =
        run(HYPRSTACK_SYSTEMCTL,
            {"show", "apparmor.service", "--property=UnitFileState", "--value"},
            5000);
    serviceEnabled = enabled == "enabled" || enabled == "enabled-runtime";
  } catch (const Failure &) {
  }
  return {{"apparmorServiceEnabled", serviceEnabled},
          {"apparmorServiceState", serviceState},
          {"available", true},
          {"apparmorActive", active},
          {"profiles", profiles},
          {"profileFiles", files},
          {"pacmanAvailable", !QString(HYPRSTACK_PACMAN).isEmpty()}};
}
void validateApplications(const QString &op, const QJsonObject &o) {
  if (op == "service-enable") {
    if (o.size() != 1 || !o["enabled"].isBool())
      throw Failure("invalid", "Invalid AppArmor service request");
    return;
  }
  if (op == "profile-controls") {
    if(o.size()!=4 || !o["restrictions"].isObject() ||
       !QRegularExpression("^[a-f0-9]{64}$").match(o["sha256"].toString()).hasMatch() ||
       !QRegularExpression("^[a-f0-9]{64}$").match(o["localSha256"].toString()).hasMatch())
      throw Failure("invalid","Invalid AppArmor controls");
    profileFile(o);HicsArmor::rules(o["restrictions"].toObject());return;
  }
  if (op == "profile-save") {
    if (o.size() != 3 || !o["content"].isString() ||
        o["content"].toString().toUtf8().size() > 65536 ||
        !QRegularExpression("^[a-f0-9]{64}$")
             .match(o["sha256"].toString())
             .hasMatch())
      throw Failure("invalid", "Invalid AppArmor policy update");
    profileFile(o);
    return;
  }
  if (op == "remove") {
    if (o.size() != 2 || !o["desktop"].isString() || !o["version"].isString())
      throw Failure("invalid", "Invalid application removal request");
    packageFor(o);
    return;
  }
  if (QStringList{"enforce", "complain", "disable-profile"}.contains(op)) {
    if (o.size() != 1)
      throw Failure("invalid", "Invalid AppArmor request");
    profileFile(o);
    return;
  }
  throw Failure("invalid", "Unknown application administration operation");
}
void applyApplications(const QString &op, const QJsonObject &o) {
  static QMutex mutation;
  if (!mutation.tryLock())
    throw Failure("busy",
                  "An application administration task is already running");
  const auto unlock = qScopeGuard([&] { mutation.unlock(); });
  validateApplications(op, o);
  if (op == "service-enable") {
    rootTask(HYPRSTACK_SYSTEMCTL,
             {o["enabled"].toBool() ? "enable" : "disable", "--now",
              "apparmor.service"},
             "Configure AppArmor startup");
    return;
  }
  if (op == "profile-controls") {
    const auto path=profileFile(o),name=QFileInfo(path).fileName();
    QFile main(path);if(!main.open(QIODevice::ReadOnly)||main.size()>65536)throw Failure("invalid","Profile unavailable");
    const auto bytes=main.readAll();
    if(!HicsArmor::supported(bytes,name))throw Failure("unsupported","This profile has no standard local include; use advanced policy editing");
    const auto digest=[](const QByteArray &data){return QString::fromLatin1(QCryptographicHash::hash(data,QCryptographicHash::Sha256).toHex());};
    const auto directory=QString("/etc/apparmor.d/local");
    QFileInfo dir(directory);
    if(!dir.exists()&&!dir.isSymLink()) {
      if(!QDir().mkpath(directory)||!QFile::setPermissions(directory,QFileDevice::ReadOwner|QFileDevice::WriteOwner|QFileDevice::ExeOwner|QFileDevice::ReadGroup|QFileDevice::ExeGroup|QFileDevice::ReadOther|QFileDevice::ExeOther))throw Failure("failed","Cannot create AppArmor local policy directory");
      dir.refresh();
    }
    if(!dir.isDir()||dir.isSymLink()||dir.ownerId()!=0||dir.canonicalFilePath()!=directory ||
       (dir.permissions()&(QFileDevice::WriteGroup|QFileDevice::WriteOther)))throw Failure("invalid","Unsafe AppArmor local policy directory");
    const auto target=directory+"/"+name;
    QFile local(target);QByteArray before;
    if(local.exists()) {
      QFileInfo info(target);
      if(info.isSymLink()||info.ownerId()!=0||(info.permissions()&(QFileDevice::WriteGroup|QFileDevice::WriteOther))||!local.open(QIODevice::ReadOnly)||local.size()>65536)
        throw Failure("invalid","Unsafe local policy file");
      before=local.readAll();local.close();
    }
    if(digest(bytes)!=o["sha256"].toString()||digest(before)!=o["localSha256"].toString())throw Failure("changed","Policy changed; select the profile again");
    const auto settings=o["restrictions"].toObject();
    const auto after=HicsArmor::merge(before,settings);
    if(after.size()>65536)throw Failure("invalid","Local policy is too large");
    QTemporaryFile validation;
    const auto fragment=QByteArray("#include <tunables/global>\nprofile hics-controls-validation {\n")+HicsArmor::rules(settings)+"}\n";
    if(!validation.open()||validation.write(fragment)!=fragment.size()||!validation.flush())throw Failure("failed","Cannot validate controls");
    run(HYPRSTACK_APPARMOR_PARSER,{"--skip-kernel-load","--skip-cache","--jobs=1","--max-jobs=1","--base","/etc/apparmor.d",validation.fileName()},30000);
    if(!before.isEmpty()) {
      const auto backupDir=QString("/var/lib/hics/apparmor-backups");QDir().mkpath(backupDir);
      QFile::setPermissions(backupDir,QFileDevice::ReadOwner|QFileDevice::WriteOwner|QFileDevice::ExeOwner);
      QFile backup(backupDir+"/local."+name+"."+QString::number(QDateTime::currentMSecsSinceEpoch()));
      if(!backup.open(QIODevice::WriteOnly|QIODevice::NewOnly)||!backup.setPermissions(QFileDevice::ReadOwner|QFileDevice::WriteOwner)||backup.write(before)!=before.size())throw Failure("failed","Cannot back up local policy");
    }
    QSaveFile output(target);
    if(!output.open(QIODevice::WriteOnly)||!output.setPermissions(QFileDevice::ReadOwner|QFileDevice::WriteOwner|QFileDevice::ReadGroup|QFileDevice::ReadOther)||output.write(after)!=after.size()||!output.commit())throw Failure("failed","Cannot save local policy");
    return;
  }
  if (op == "profile-save") {
    const auto path = profileFile(o);
    QFile original(path);
    if (!original.open(QIODevice::ReadOnly) || original.size() > 65536)
      throw Failure("invalid", "Profile is unavailable or too large");
    const auto before = original.readAll();
    if (QString::fromLatin1(
            QCryptographicHash::hash(before, QCryptographicHash::Sha256)
                .toHex()) != o["sha256"].toString())
      throw Failure("changed", "The profile changed; reload it before saving");
    const auto bytes = o["content"].toString().toUtf8();
    QTemporaryFile candidate;
    if (!candidate.open() || candidate.write(bytes) != bytes.size() ||
        !candidate.flush())
      throw Failure("failed", "Cannot prepare AppArmor policy");
    run(HYPRSTACK_APPARMOR_PARSER,
        {"--skip-kernel-load", "--skip-cache", "--jobs=1", "--max-jobs=1",
         "--base", "/etc/apparmor.d", candidate.fileName()},
        30000);
    const auto backupDir = QString("/var/lib/hics/apparmor-backups");
    QDir().mkpath(backupDir);
    QFile::setPermissions(backupDir, QFileDevice::ReadOwner |
                                         QFileDevice::WriteOwner |
                                         QFileDevice::ExeOwner);
    const auto backup = backupDir + "/" + QFileInfo(path).fileName() + "." +
                        QString::number(QDateTime::currentMSecsSinceEpoch());
    QFile snapshot(backup);
    if (!snapshot.open(QIODevice::WriteOnly | QIODevice::NewOnly) ||
        !snapshot.setPermissions(QFileDevice::ReadOwner |
                                 QFileDevice::WriteOwner) ||
        snapshot.write(before) != before.size())
      throw Failure("failed", "Cannot save the previous profile");
    snapshot.close();
    QSaveFile output(path);
    if (!output.open(QIODevice::WriteOnly) ||
        !output.setPermissions(original.permissions()) ||
        output.write(bytes) != bytes.size() || !output.commit())
      throw Failure("failed", "Cannot save AppArmor profile");
    return;
  }
  if (op == "remove") {
    const auto package = packageFor(o);
    rootTask(HYPRSTACK_PACMAN, {"-R", "--noconfirm", "--", package},
             "Remove application");
    return;
  }
  const auto executable = op == "enforce"    ? QString(HYPRSTACK_AA_ENFORCE)
                          : op == "complain" ? QString(HYPRSTACK_AA_COMPLAIN)
                                             : QString(HYPRSTACK_AA_DISABLE);
  if (executable.isEmpty())
    throw Failure("unavailable",
                  "AppArmor administration tools are not installed");
  rootTask(executable, {profileFile(o)}, "Change AppArmor profile mode");
}
} // namespace System
