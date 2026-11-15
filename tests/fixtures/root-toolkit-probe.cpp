#include <QApplication>
#include <QPalette>
#include <QStyleHints>
#include <QJsonObject>
#include <QJsonDocument>
#include <QQmlEngine>
#include <QQmlComponent>
#include <cstdio>
int main(int argc,char**argv){QApplication app(argc,argv);QJsonObject r{{"window",app.palette().color(QPalette::Window).name()}};
#if QT_VERSION >= QT_VERSION_CHECK(6,5,0)
r["scheme"]=int(app.styleHints()->colorScheme());
#endif
if(argc>1){QQmlEngine engine;QQmlComponent c(&engine);QByteArray style=argv[1];QByteArray version=QT_VERSION_MAJOR<6 ? " 2.15" : "";c.setData("import QtQuick"+version+"\nimport QtQuick.Controls"+version+"\nimport QtQuick.Controls."+style+version+"\nApplicationWindow {property bool dark: "+style+".theme === "+style+".Dark}",QUrl());auto*o=c.create();if(!o){for(const auto &error:c.errors())fprintf(stderr,"%s\n",error.toString().toLocal8Bit().constData());return 1;}r["quickDark"]=o->property("dark").toBool();delete o;}
puts(QJsonDocument(r).toJson(QJsonDocument::Compact).constData());}
