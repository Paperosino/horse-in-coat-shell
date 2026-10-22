#include "workspacetools.hpp"
#include "workspacestore.hpp"
#include <QCoreApplication>
#include <QEventLoop>
#include <QJsonDocument>
#include <QTimer>
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
   if(mode=="capture-and-autosave"){session.capture("Manual",false);wait();session.capture("Automatic",true);}
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
