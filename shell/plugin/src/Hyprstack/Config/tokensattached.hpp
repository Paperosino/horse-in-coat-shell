#pragma once

#include <qqmlintegration.h>
#include <qqmlparserstatus.h>
#include <qquickattachedpropertypropagator.h>

#include "anim.hpp"
#include "font.hpp"
#include "rootnodes.hpp"

namespace hyprstack::config {

class Tokens : public QQuickAttachedPropertyPropagator, public QQmlParserStatus {
    Q_OBJECT
    Q_INTERFACES(QQmlParserStatus)
    QML_ELEMENT
    QML_UNCREATABLE("")
    QML_ATTACHED(Tokens)

    Q_PROPERTY(QString screen READ screen WRITE inheritScreen NOTIFY sourceChanged)
    Q_PROPERTY(const hyprstack::config::AppearanceRounding* rounding READ rounding NOTIFY sourceChanged)
    Q_PROPERTY(const hyprstack::config::AppearanceSpacing* spacing READ spacing NOTIFY sourceChanged)
    Q_PROPERTY(const hyprstack::config::AppearancePadding* padding READ padding NOTIFY sourceChanged)
    Q_PROPERTY(const hyprstack::config::AppearanceTransparency* transparency READ transparency NOTIFY sourceChanged)
    Q_PROPERTY(qreal scale READ scale NOTIFY scaleChanged)
    Q_PROPERTY(const hyprstack::config::ScaledSizeTokens* sizes READ sizes NOTIFY sourceChanged)
    Q_PROPERTY(const hyprstack::config::FontTokens* font READ font NOTIFY sourceChanged)
    Q_PROPERTY(const hyprstack::config::AnimTokens* anim READ anim NOTIFY sourceChanged)

public:
    explicit Tokens(QObject* parent = nullptr);

    [[nodiscard]] QString screen() const;
    void inheritScreen(const QString& screen);

    [[nodiscard]] const AppearanceRounding* rounding() const;
    [[nodiscard]] const AppearanceSpacing* spacing() const;
    [[nodiscard]] const AppearancePadding* padding() const;
    [[nodiscard]] static const AppearanceTransparency* transparency();

    [[nodiscard]] qreal scale() const;
    [[nodiscard]] const ScaledSizeTokens* sizes() const;
    [[nodiscard]] const FontTokens* font() const;
    [[nodiscard]] const AnimTokens* anim() const;

    [[nodiscard]] Q_INVOKABLE static TokensRoot* forScreen(const QString& screen);

    static Tokens* qmlAttachedProperties(QObject* object);

    void classBegin() override;
    void componentComplete() override;

signals:
    void sourceChanged();
    void scaleChanged();

protected:
    void attachedParentChange(
        QQuickAttachedPropertyPropagator* newParent, QQuickAttachedPropertyPropagator* oldParent) override;

private:
    void propagateScreen();
    void bindAnim();
    void bindFont();

    bool m_complete = false;
    QString m_screen;
    ConfigRoot* m_config = nullptr;
    TokensRoot* m_tokens = nullptr;
    FontTokens* m_font = nullptr;
    AnimTokens* m_anim = nullptr;
    QMetaObject::Connection m_scaleConnection;
};

} // namespace hyprstack::config
