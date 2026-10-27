#include "logging.hpp"
#include <QCoreApplication>
#include <QTimer>
#include <cstdio>
int main(int argc,char**argv) {
 QCoreApplication app(argc,argv);
 QByteArray name(400,'x');name.replace(0,10,"fixturecat");
 qs::log::LogMessage first(QtWarningMsg,QLatin1StringView(name),QByteArray("body"));
 qs::log::LogMessage copy=first;
 qs::log::LogMessage moved=std::move(copy);
 QTimer::singleShot(0,&app,[moved]{
  QByteArray expected(400,'x');expected.replace(0,10,"fixturecat");
  if(moved.category!=QLatin1StringView(expected))std::abort();
  std::fprintf(stdout,"Owned queued category survived input and source-message destruction\n");
  QCoreApplication::quit();
 });
 name.clear();name.squeeze();first=qs::log::LogMessage();moved=qs::log::LogMessage();
 return app.exec();
}
