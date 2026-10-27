#include "iutils.hpp"
#include <QGuiApplication>
#include <QQmlEngine>
#include <QQmlContext>
#include <QQmlComponent>
#include <QQuickItem>
#include <QQuickItemGrabResult>
#include <QQuickWindow>
#include <QImage>
#include <QFile>
#include <QFileInfo>
#include <QDir>
#include <QBuffer>
#include <QSaveFile>
#include <QDateTime>
#include <QEventLoop>
#include <QTimer>
#include <QJsonDocument>
#include <QJsonObject>
#include <QTextStream>
#include <sys/stat.h>
#include <memory>
#include <functional>
#include <stdexcept>
using hyprstack::images::IUtils;
void check(bool ok,const char *message) { if (!ok) throw std::runtime_error(message); }
bool waitFor(const std::function<bool()> &condition,int milliseconds=3000) {
    if (condition()) return true;
    QEventLoop loop;QTimer poll,deadline;
    QObject::connect(&poll,&QTimer::timeout,&loop,[&] {if(condition())loop.quit();});
    QObject::connect(&deadline,&QTimer::timeout,&loop,&QEventLoop::quit);
    poll.start(10);deadline.setSingleShot(true);deadline.start(milliseconds);loop.exec();return condition();
}
void settle(int ms=150) {QEventLoop loop;QTimer::singleShot(ms,&loop,&QEventLoop::quit);loop.exec();}
void save(const QString &path,Qt::GlobalColor colour) {
    QImage image(24,16,QImage::Format_RGB32);image.fill(colour);
    QByteArray bytes;QBuffer buffer(&bytes);buffer.open(QIODevice::WriteOnly);check(image.save(&buffer,"BMP"),"Cannot encode fixture");
    QSaveFile file(path);check(file.open(QIODevice::WriteOnly),"Cannot open fixture");
    check(file.write(bytes)==bytes.size()&&file.commit(),"Cannot publish fixture");
}
QColor pixel(QQuickItem *item) {
    auto grab=item->grabToImage();check(bool(grab),"Cannot start image grab");
    check(waitFor([&] {return !grab->image().isNull();}),"Image grab timed out");
    return grab->image().pixelColor(8,8);
}
int main(int argc,char **argv) {
    QGuiApplication app(argc,argv);
    try {
        const auto face=QDir::home().filePath(".face");
        if(app.arguments().value(1)=="fifo")check(::mkfifo(QFile::encodeName(face),0600)==0,"Cannot create FIFO");
        QQuickWindow window;window.resize(16,16);window.show();
        QQmlEngine engine;auto *avatar=IUtils::create(&engine,&engine);
        engine.rootContext()->setContextProperty("avatar",avatar);
        QQmlComponent component(&engine);component.setData("import QtQuick\nImage {width:16;height:16;asynchronous:true;fillMode:Image.PreserveAspectCrop;sourceSize:Qt.size(16,16);source:avatar.profilePicture}",QUrl());
        std::unique_ptr<QQuickItem> item(qobject_cast<QQuickItem*>(component.create()));
        check(bool(item),qPrintable(component.errorString()));item->setParentItem(window.contentItem());
        int events=0;QObject::connect(avatar,&IUtils::profilePictureChanged,&app,[&] {++events;});
        check(avatar->profilePicture().isEmpty(),"Missing/non-regular avatar has a source");
        check(item->property("status").toInt()==0,"Absent avatar attempted an image decode");
        if(app.arguments().value(1)=="fifo") {settle();puts("FIFO_OK");return 0;}
        save(face,Qt::red);
        check(waitFor([&]{return !avatar->profilePicture().isEmpty()&&item->property("status").toInt()==1;}),"Created avatar did not appear");
        check(pixel(item.get())==QColor(Qt::red),"Created avatar pixels are incorrect");
        const auto oldUrl=avatar->profilePicture();const auto oldTime=QFileInfo(face).lastModified();const auto oldSize=QFileInfo(face).size();
        save(face,Qt::blue);
        {QFile file(face);check(file.open(QIODevice::ReadWrite)&&file.setFileTime(oldTime,QFileDevice::FileModificationTime),"Cannot preserve fixture mtime");}
        check(QFileInfo(face).size()==oldSize,"Fixture size changed");
        check(waitFor([&]{return avatar->profilePicture()!=oldUrl&&item->property("status").toInt()==1;}),"Atomic replacement did not invalidate source");
        check(waitFor([&]{return pixel(item.get())==QColor(Qt::blue);}),"Disk/texture cache retained old pixels");
        const auto beforeUnrelated=avatar->profilePicture();const auto beforeEvents=events;
        {QFile file(QDir::home().filePath("unrelated"));check(file.open(QIODevice::WriteOnly),"Cannot create unrelated file");}
        settle();check(avatar->profilePicture()==beforeUnrelated&&events==beforeEvents,"Unrelated home change reloaded avatar");
        check(QFile::remove(face),"Cannot delete avatar");
        check(waitFor([&]{return avatar->profilePicture().isEmpty()&&item->property("status").toInt()==0;}),"Deleted avatar did not return to fallback");
        const auto target=QDir::home().filePath("target.bmp");save(target,Qt::green);check(QFile::link(target,face),"Cannot link avatar");
        check(waitFor([&]{return !avatar->profilePicture().isEmpty()&&item->property("status").toInt()==1;}),"Symlink avatar did not appear");
        check(pixel(item.get())==QColor(Qt::green),"Symlink avatar pixels are incorrect");
        const auto linkUrl=avatar->profilePicture();save(target,Qt::yellow);
        check(waitFor([&]{return avatar->profilePicture()!=linkUrl&&item->property("status").toInt()==1;}),"Replaced symlink target did not invalidate avatar");
        check(waitFor([&]{return pixel(item.get())==QColor(Qt::yellow);}),"Symlink target retained old pixels");
        // Ordinary cached images must retain URL escaping for reserved/unicode names.
        for(const auto &name : {QString::fromUtf8("тест % ? #.bmp"),QString("literal%2F.bmp")}) {
            const auto file=QDir::home().filePath(name);save(file,Qt::cyan);
            item->setProperty("source",IUtils::urlForPath(file,2));
            check(waitFor([&]{return item->property("status").toInt()==1;}),"Escaped image failed to load");
            check(pixel(item.get())==QColor(Qt::cyan),"Escaped image pixels are incorrect");
        }
        check(avatar->findChildren<QFileSystemWatcher*>().size()==1,"Avatar duplicated filesystem observers");
        settle();for(auto *timer:avatar->findChildren<QTimer*>())check(!timer->isActive(),"Avatar polls while idle");
        puts("PROFILE_PICTURE_OK");return 0;
    } catch (const std::exception &e) {QTextStream(stderr)<<e.what()<<Qt::endl;return 1;}
}
