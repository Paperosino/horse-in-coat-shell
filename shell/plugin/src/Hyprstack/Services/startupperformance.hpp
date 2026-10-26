#pragma once
#include <QObject>
#include <QQmlEngine>
#include <QSet>
class QQuickWindow;
namespace hyprstack::services {
class StartupPerformance final : public QObject {
    Q_OBJECT
    QML_ELEMENT
    QML_SINGLETON
    Q_PROPERTY(bool firstFrame READ firstFrame NOTIFY firstFrameChanged)
public:
    explicit StartupPerformance(QObject *parent=nullptr);
    ~StartupPerformance() override;
    bool firstFrame() const {return m_firstFrame;}
    bool eventFilter(QObject *object,QEvent *event) override;
signals:
    void firstFrameChanged();
private:
    void watch(QQuickWindow *window);
    bool m_firstFrame=false;
    QSet<QQuickWindow*> m_windows;
};
}
