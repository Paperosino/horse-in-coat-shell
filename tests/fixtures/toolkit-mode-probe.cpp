#include <QApplication>
#include <QPalette>
#include <QQmlEngine>
#include <QQmlComponent>
#include <QJsonDocument>
#include <QJsonObject>
#include <cstdio>
int main(int argc,char**argv){
 QApplication app(argc,argv);QQmlEngine engine;QQmlComponent component(&engine);
 const auto style=QString::fromLocal8Bit(argv[1]);
 component.setData(("import QtQuick\nimport QtQuick.Controls\nimport QtQuick.Controls."+style+"\nApplicationWindow {property bool dark: "+style+".theme === "+style+".Dark}").toUtf8(),QUrl());
 auto*object=component.create();if(!object){qWarning()<<component.errors();return 1;}
 auto json=QJsonDocument(QJsonObject{{"dark",object->property("dark").toBool()},{"window",app.palette().color(QPalette::Window).name()}}).toJson(QJsonDocument::Compact);
 puts(json.constData());delete object;return 0;
}
