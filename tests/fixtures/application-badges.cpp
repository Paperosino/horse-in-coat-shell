#include "applicationbadges.hpp"
#include <QCoreApplication>
#include <QDBusConnection>
#include <QTimer>
#include <QTextStream>
using namespace hyprstack::services;
int main(int argc,char**argv){
 QCoreApplication app(argc,argv);ApplicationBadges badges;
 auto sender=QDBusConnection::connectToBus(QDBusConnection::SessionBus,QStringLiteral("badge-test"));
 auto send=[&sender](QString uri,QVariantMap properties){auto message=QDBusMessage::createSignal(QStringLiteral("/org/hics/TestBadge"),QStringLiteral("com.canonical.Unity.LauncherEntry"),QStringLiteral("Update"));message<<uri<<properties;return sender.send(message);};
 int phase=0;
 QTimer timer;timer.setInterval(80);
 QObject::connect(&timer,&QTimer::timeout,&app,[&]{
  auto fail=[&]{QTextStream(stderr)<<"badge phase "<<phase<<" failed\n";app.exit(1);};
  const auto id=QStringLiteral("org.hics.fixture");
  if(phase==0){if(!send(QStringLiteral("application://org.hics.Fixture.desktop"),{{QStringLiteral("count"),qlonglong(12)},{QStringLiteral("count-visible"),true}}))return fail();}
  if(phase==1){if(badges.entries().value(id).toMap().value(QStringLiteral("count")).toInt()!=12)return fail();send(QStringLiteral("application://org.hics.Fixture.desktop"),{{QStringLiteral("count"),qlonglong(100)}});}
  if(phase==2){auto value=badges.entries().value(id).toMap();if(value.value(QStringLiteral("count")).toInt()!=100||!value.value(QStringLiteral("visible")).toBool())return fail();send(QStringLiteral("application://../../bad.desktop"),{{QStringLiteral("count"),5}});send(QStringLiteral("application://org.hics.Fixture.desktop"),{{QStringLiteral("count-visible"),false}});}
  if(phase==3){if(badges.entries().size()!=1||badges.entries().value(id).toMap().value(QStringLiteral("visible")).toBool())return fail();QDBusConnection::disconnectFromBus(QStringLiteral("badge-test"));sender=QDBusConnection(QStringLiteral("closed"));}
  if(phase==4){if(!badges.entries().isEmpty())return fail();app.exit(0);}
  ++phase;
 });timer.start();QTimer::singleShot(3000,&app,[&]{app.exit(2);});return app.exec();
}
