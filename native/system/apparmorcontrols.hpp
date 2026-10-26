#pragma once
#include <QJsonDocument>
#include <QJsonObject>
#include <QRegularExpression>
#include <stdexcept>
namespace HicsArmor {
inline const QByteArray Begin="# BEGIN hics GUI restrictions\n";
inline const QByteArray End="# END hics GUI restrictions\n";
inline QStringList keys(){return {QStringLiteral("network"),QStringLiteral("camera"),QStringLiteral("audio"),QStringLiteral("home"),QStringLiteral("removable")};}
inline bool supported(const QByteArray &main,const QString &profile) {
    return QRegularExpression(QStringLiteral("^\\s*#?include\\s+(?:if\\s+exists\\s+)?<local/")+QRegularExpression::escape(profile)+QStringLiteral(">\\s*(?:#[^\\n]*)?$"),QRegularExpression::MultilineOption).match(QString::fromUtf8(main)).hasMatch();
}
inline QJsonObject settings(const QByteArray &local) {
    QJsonObject result;for(const auto &key:keys())result[key]=false;
    const auto start=local.indexOf(Begin);if(start<0)return result;
    const auto dataStart=start+Begin.size();
    const auto end=local.indexOf('\n',dataStart);
    const auto line=local.mid(dataStart,end-dataStart);
    const QByteArray prefix="# hics-controls: ";
    if(line.startsWith(prefix)) {
        const auto saved=QJsonDocument::fromJson(line.mid(prefix.size())).object();
        for(const auto &key:keys())if(saved[key].isBool())result[key]=saved[key];
    }
    return result;
}
inline QByteArray rules(const QJsonObject &settings) {
    for(auto it=settings.begin();it!=settings.end();++it)
        if(!keys().contains(it.key())||!it.value().isBool())throw std::runtime_error("Invalid AppArmor control");
    QByteArray out;
    if(settings[QStringLiteral("network")].toBool())out+="deny network inet,\ndeny network inet6,\n";
    if(settings[QStringLiteral("camera")].toBool())out+="deny /dev/video[0-9]* rw,\ndeny /dev/media[0-9]* rw,\n";
    if(settings[QStringLiteral("audio")].toBool())out+="deny /dev/snd/** rw,\n";
    if(settings[QStringLiteral("home")].toBool())out+="deny @{HOME}/** rwklm,\n";
    if(settings[QStringLiteral("removable")].toBool())out+="deny /media/** rwklm,\ndeny /run/media/** rwklm,\ndeny /mnt/** rwklm,\n";
    return out;
}
inline QByteArray merge(QByteArray local,const QJsonObject &settings) {
    const auto start=local.indexOf(Begin),end=local.indexOf(End);
    if((start<0)!=(end<0)||(start>=0&&(end<start||local.indexOf(Begin,start+1)>=0||local.indexOf(End,end+1)>=0)))
        throw std::runtime_error("Managed AppArmor block changed; inspect the local policy first");
    if(start>=0)local.remove(start,end+End.size()-start);
    if(!local.isEmpty()&&!local.endsWith('\n'))local+='\n';
    return local+Begin+"# hics-controls: "+QJsonDocument(settings).toJson(QJsonDocument::Compact)+'\n'+rules(settings)+End;
}
}
