#include "startupperformance.hpp"
#include <QGuiApplication>
#include <QQuickWindow>
#include <QEvent>
#include <QDebug>
#include <QPointer>
namespace hyprstack::services {
StartupPerformance::StartupPerformance(QObject *parent):QObject(parent) {
    qGuiApp->installEventFilter(this);
    for(auto *window:QGuiApplication::allWindows())if(auto *quick=qobject_cast<QQuickWindow*>(window))watch(quick);
}
StartupPerformance::~StartupPerformance(){if(qGuiApp)qGuiApp->removeEventFilter(this);}
bool StartupPerformance::eventFilter(QObject *object,QEvent *event) {
    if(!m_firstFrame&&(event->type()==QEvent::Show||event->type()==QEvent::Expose))
        if(auto *window=qobject_cast<QQuickWindow*>(object))watch(window);
    return false;
}
void StartupPerformance::watch(QQuickWindow *window) {
    if(m_windows.contains(window))return;
    m_windows.insert(window);
    connect(window,&QObject::destroyed,this,[this,window]{m_windows.remove(window);});
    const QPointer<QQuickWindow> guarded=window;
    connect(window,&QQuickWindow::frameSwapped,this,[this,guarded] {
        auto *observedWindow=guarded.data();
        if(!observedWindow)return;
        if(m_firstFrame||!observedWindow->isVisible()||observedWindow->width()<=0||observedWindow->height()<=0)return;
        m_firstFrame=true;
        qGuiApp->removeEventFilter(this);
        qInfo("hics startup: first visible frame submitted");
        for(auto *observed:m_windows)QObject::disconnect(observed,nullptr,this,nullptr);
        m_windows.clear();
        emit firstFrameChanged();
    },Qt::QueuedConnection);
}
}
