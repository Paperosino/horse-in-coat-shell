#include "workspacetools.hpp"
#include "workspacestore.hpp"
#include <QCoreApplication>
#include <QEventLoop>
#include <QJsonDocument>
#include <QTimer>
#include <QDir>
#include <QFile>
#include <QElapsedTimer>
#include <QThread>
#include <cstdio>
using namespace hyprstack::services;
namespace W=hics::workspace;
int main(int argc,char **argv){
 QCoreApplication app(argc,argv);auto args=app.arguments();const auto mode=args.value(1);QVariantMap result;
 try{
  auto json=[&](int n){return QJsonDocument::fromJson(args.value(n).toUtf8()).toVariant().toMap();};
  if(mode=="settings"){W::setSettings(args.value(2),json(3));result=W::settings(args.value(2));}
  else if(mode=="clipboard-store"){result["stored"]=W::storeClipboard(args.value(2).toUtf8(),args.value(3,"text/plain"),args.value(4));result["entries"]=W::clipboardEntries();}
  else if(mode=="clipboard-pin"||mode=="clipboard-delete"){W::alterClipboard(args.value(2),mode=="clipboard-pin"?"pin":"delete");result["entries"]=W::clipboardEntries();}
  else if(mode=="clipboard-clear"){W::clearClipboard(args.value(2)=="keep");result["entries"]=W::clipboardEntries();}
  else if(mode=="clipboard-read"){result["text"]=QString::fromUtf8(W::clipboardData(args.value(2)));}
  else if(mode=="clipboard-path"){result["path"]=W::clipboardFile(args.value(2));}
  else if(mode=="destroy-session"){
   auto *session=new WorkspaceSession;session->restore(args.value(2));
   QElapsedTimer started;started.start();
   const auto marker=args.value(3);
   while(!QFile::exists(marker)&&started.elapsed()<3000){app.processEvents();QThread::msleep(10);}
   result["started"]=QFile::exists(marker);started.restart();delete session;
   result["destroyMs"]=started.elapsed();
  }
  else if(mode=="clipboard-list")result["entries"]=W::clipboardEntries();
  else if(mode=="record-key"){ShortcutEditor editor;editor.refresh();result["chord"]=editor.recordKey(args.value(2).toInt(),args.value(3).toInt(),args.value(4).toInt());}
  else if(mode=="chord")result["chord"]=W::normalizedChord(args.value(2));
  else if(mode.startsWith("shortcut")){
   ShortcutEditor editor;editor.refresh();
   if(mode=="shortcut-save")editor.save(json(2));
   if(mode=="shortcut-reset")editor.reset(args.value(2));
   if(mode=="shortcut-import")editor.importFile(QUrl::fromLocalFile(args.value(2)));
   result={{"error",editor.error()},{"actions",editor.actions()},{"settings",W::settings("shortcuts")}};
  }else{
   WorkspaceSession session;session.refresh();
   auto wait=[&]{if(!session.busy())return;QEventLoop loop;QObject::connect(&session,&WorkspaceSession::finished,&loop,&QEventLoop::quit);QTimer::singleShot(15000,&loop,&QEventLoop::quit);loop.exec();};
   if(mode=="watch-session") {
    int changes=0, baseline=0;
    bool created=false, updated=false, retained=false, recovered=false, removed=false;
    QObject::connect(&session,&WorkspaceSession::changed,&app,[&]{++changes;});
    const auto path=W::statePath()+"/sessions/watch.json";
    auto write=[&](const QString &name){W::writeMap(path,{{"name",name},{"windows",QVariantList{QVariantMap{}}}});};
    QEventLoop loop;
    QTimer::singleShot(300,&loop,[&]{baseline=changes;});
    QTimer::singleShot(650,&loop,[&]{result["idle"]=changes==baseline;write("First");});
    QTimer::singleShot(1000,&loop,[&]{created=session.snapshots().size()==1;write("Second");});
    QTimer::singleShot(1350,&loop,[&]{updated=session.snapshots().value(0).toMap().value("name")=="Second";QFile f(path);if(f.open(QIODevice::WriteOnly))f.write("{");});
    QTimer::singleShot(1700,&loop,[&]{retained=session.snapshots().value(0).toMap().value("name")=="Second"&&!session.error().isEmpty();write("Recovered");});
    QTimer::singleShot(2050,&loop,[&]{recovered=session.snapshots().value(0).toMap().value("name")=="Recovered"&&session.error().isEmpty();QFile::remove(path);});
    QTimer::singleShot(2400,&loop,[&]{removed=session.snapshots().isEmpty();loop.quit();});
    loop.exec();
    result.insert("created",created);result.insert("updated",updated);result.insert("retained",retained);result.insert("recovered",recovered);result.insert("removed",removed);
    puts(QJsonDocument::fromVariant(result).toJson(QJsonDocument::Compact).constData());return 0;
   }
   if(mode=="capture-and-autosave"){session.capture("Manual",false);wait();session.capture("Automatic",true);}
   else if(mode=="capture-project")session.captureProject(args.value(2,"Project"),args.value(3,"0").toInt(),args.value(4,"3").toInt(),"stacking",true);
   else if(mode=="capture")session.capture(args.value(2,"Fixture"),args.value(3)=="automatic");
   else if(mode=="import-desktop")session.importDesktop(args.value(2));
   else if(mode=="import-file")session.importFile(QUrl::fromLocalFile(args.value(2)));
   else if(mode=="restore")session.restore(args.value(2));
   else if(mode=="save-preview")session.savePreview(json(2));
   else if(mode=="session-configure")session.configure(json(2));
   else if(mode=="export")session.exportFile(args.value(2),QUrl::fromLocalFile(args.value(3)),args.value(4)=="portable");
   wait();result={{"error",session.error()},{"preview",session.preview()},{"report",session.report()},{"snapshots",session.snapshots()}};
  }
 }catch(const std::exception &e){result={{"error",QString::fromUtf8(e.what())}};}
 puts(QJsonDocument::fromVariant(result).toJson(QJsonDocument::Compact).constData());
}
