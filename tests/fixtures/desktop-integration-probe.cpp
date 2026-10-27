#include "desktopintegration.hpp"
#include "notificationpolicy.hpp"
#include <QCoreApplication>
#include <QEventLoop>
#include <QFile>
#include <QJsonDocument>
#include <QJsonArray>
#include <QJsonObject>
#include <QTextStream>
#include <QTimer>
#include <QProcess>
#include <QDBusPendingCallWatcher>
using namespace hyprstack::services;
int main(int argc, char **argv) {
    QCoreApplication app(argc, argv);
    const auto request = QJsonDocument::fromJson(QTextStream(stdin).readAll().toUtf8()).object();
    const auto operation = request["operation"].toString();
    QJsonObject result;
    if (operation.startsWith("policy")) {
        NotificationPolicy policy;
        if (operation == "policy-write") {
            policy.observe("org.example.Chat", "Chat");
            policy.setRule("org.example.Chat", "silent");
            policy.pauseFor(30);
        } else if (operation == "policy-resume") policy.resume();
        result = {{"paused", policy.paused()}, {"until", policy.pausedUntil()},
            {"rule", policy.rule("org.example.Chat")}, {"applications", QJsonArray::fromVariantList(policy.applications())}, {"error", policy.error()}};
    } else if (operation == "destroy-active") {
        auto *desktop = new DesktopIntegration;
        bool destroyed = false;
        QObject::connect(desktop,&QObject::destroyed,&app,[&] { destroyed = true; });
        desktop->refresh();
        QEventLoop loop;
        QTimer::singleShot(500,&app,[desktop] { delete desktop; });
        QTimer::singleShot(4300,&loop,&QEventLoop::quit);loop.exec();
        result = {{"destroyed",destroyed}};
    } else {
        DesktopIntegration desktop;
        bool succeeded = false;
        QObject::connect(&desktop, &DesktopIntegration::operationSucceeded, &app, [&] { succeeded = true; });
        if (operation == "refresh" || operation == "portal-retry") desktop.refresh();
        else if (operation == "monitor") {
            desktop.refreshMonitoring();
            desktop.refreshMonitoring(); // overlapping poll must be coalesced
        }
        else if (operation == "profile") desktop.setCardProfile(request["card"].toString(), request["profile"].toString());
        else if (operation == "hotspot") desktop.startHotspot(request["path"].toString(), request["ssid"].toString(), request["password"].toString());
        else if (operation == "hidden") desktop.connectHiddenNetwork(request["ssid"].toString(), request["password"].toString(), true, true);
        else if (operation == "stop-hotspot") desktop.stopHotspot(request["path"].toString());
        else if (operation == "unlock") desktop.unlockVolume(request["path"].toString(), request["password"].toString());
        else if (operation == "lock") desktop.lockVolume(request["path"].toString());
        else if (operation == "eject") desktop.ejectDrive(request["path"].toString(), true);
        const auto waitIdle = [&] {
            QEventLoop loop;
            QTimer poll, deadline;
            QObject::connect(&poll, &QTimer::timeout, &loop, [&] { if (!desktop.busy()) loop.quit(); });
            QObject::connect(&deadline, &QTimer::timeout, &loop, &QEventLoop::quit);
            poll.start(10); deadline.setSingleShot(true); deadline.start(request["waitMs"].toInt(5000));
            loop.exec();
        };
        waitIdle();
        if (operation == "portal-retry") {
            QTextStream(stdout) << QJsonDocument(QJsonObject{{"readyForRetry",true},{"busy",desktop.busy()},
                {"portalSourceTypes",desktop.portalSourceTypes()}}).toJson(QJsonDocument::Compact) << Qt::endl;
            QEventLoop resume;
            QTimer poll, deadline;
            QObject::connect(&poll,&QTimer::timeout,&resume,[&] {
                if (QFile::exists(request["resumeFile"].toString())) resume.quit();
            });
            QObject::connect(&deadline,&QTimer::timeout,&resume,&QEventLoop::quit);
            poll.start(10); deadline.setSingleShot(true); deadline.start(5000); resume.exec();
            desktop.refresh(); waitIdle();
        }
        if (const int settle = request["settleMs"].toInt(); settle > 0) {
            QEventLoop loop;
            QTimer::singleShot(qMin(settle,5000),&loop,&QEventLoop::quit); loop.exec();
        }
        QJsonArray pendingProcesses;
        for (auto* process : desktop.findChildren<QProcess*>())
            if (process->state() != QProcess::NotRunning) pendingProcesses.append(process->program());
        int pendingCalls = 0;
        for (auto* call : desktop.findChildren<QDBusPendingCallWatcher*>())
            if (!call->isFinished()) ++pendingCalls;
        result = {{"pendingProcesses", pendingProcesses}, {"pendingCalls", pendingCalls}, {"portalSourceTypes", desktop.portalSourceTypes()}, {"error", desktop.error()}, {"busy", desktop.busy()}, {"succeeded", succeeded},
            {"cards", QJsonArray::fromVariantList(desktop.cards())}, {"wifi", QJsonArray::fromVariantList(desktop.wifiDevices())},
            {"encrypted", QJsonArray::fromVariantList(desktop.encryptedVolumes())}, {"drives", QJsonArray::fromVariantList(desktop.removableDrives())},
            {"captures", QJsonArray::fromVariantList(desktop.captureStreams())}, {"captureAvailable", desktop.captureMonitorAvailable()},
            {"sources", QJsonArray::fromVariantList(desktop.recordingSources())}};
    }
    QFile mappings("/proc/self/maps");
    if (mappings.open(QIODevice::ReadOnly))
        result["multimediaBackendLoaded"] = mappings.readAll().contains("/plugins/multimedia/");
    QTextStream(stdout) << QJsonDocument(result).toJson(QJsonDocument::Compact) << Qt::endl;
}
