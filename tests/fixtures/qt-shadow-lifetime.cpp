#include <QGuiApplication>
#include <QPointer>
#include <QtQuickEffects/private/qquickrectangularshadow_p.h>
#include <cstdio>

int main(int argc, char **argv) {
    QGuiApplication app(argc, argv);
    int orphaned = 0, alive = 0;
    for (int i = 0; i < 100; ++i) {
        QQuickItem custom;
        auto *shadow = new QQuickRectangularShadow;
        QPointer<QQuickItem> material = shadow->material();
        if (!material || material->parent() != shadow) ++orphaned;
        shadow->setColor(QColor("#cab0fa"));
        shadow->setRadius(12);
        shadow->setBlur(10);
        shadow->setSpread(2);
        shadow->setMaterial(&custom);
        if (shadow->material() != &custom || custom.parent()) return 2;
        shadow->setMaterial(nullptr);
        if (shadow->material() != material) return 3;
        delete shadow;
        if (material) ++alive;
    }
    printf("SHADOW_LIFETIME orphaned=%d alive=%d\n", orphaned, alive);
    return orphaned || alive ? 1 : 0;
}
