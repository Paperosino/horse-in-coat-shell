#include <QCoreApplication>
#include <QDBusConnection>
#include <QDBusMessage>
#include <QTimer>
int main(int argc,char**argv){QCoreApplication app(argc,argv);
 auto send=[](qlonglong count,bool visible){auto signal=QDBusMessage::createSignal(QStringLiteral("/org/hics/BadgeFixture"),QStringLiteral("com.canonical.Unity.LauncherEntry"),QStringLiteral("Update"));signal<<QStringLiteral("application://fixture-dock.desktop")<<QVariantMap{{QStringLiteral("count"),count},{QStringLiteral("count-visible"),visible}};QDBusConnection::sessionBus().send(signal);};
 QTimer::singleShot(250,&app,[&]{send(12,true);});QTimer::singleShot(1300,&app,[&]{send(120,true);});QTimer::singleShot(2400,&app,[&]{send(120,false);});QTimer::singleShot(3500,&app,&QCoreApplication::quit);return app.exec();}
