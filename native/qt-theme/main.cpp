#include <qpa/qplatformtheme.h>
#include <qpa/qplatformthemeplugin.h>
#include <qpa/qplatformthemefactory_p.h>
#include <QPalette>
#include <QIcon>
#include <QLibraryInfo>
#include <QVersionNumber>
#include <memory>

// qt*ct supplies the exact shell palette and fonts, but does not implement
// QPlatformTheme::colorScheme. KDE and automatic editor themes need both.
class HicsTheme final : public QPlatformTheme {
    std::unique_ptr<QPlatformTheme> m_base;
public:
    HicsTheme() : m_base(QPlatformThemeFactory::create(
#if QT_VERSION >= QT_VERSION_CHECK(6, 0, 0)
        QStringLiteral("qt6ct")
#else
        QStringLiteral("qt5ct")
#endif
    )) {}
#if QT_VERSION >= QT_VERSION_CHECK(6, 5, 0)
    Qt::ColorScheme colorScheme() const override {
        const auto *p = palette();
        if (!p) return Qt::ColorScheme::Unknown;
        return p->color(QPalette::Window).lightnessF() < .5 ? Qt::ColorScheme::Dark : Qt::ColorScheme::Light;
    }
#endif
    const QPalette *palette(Palette role = SystemPalette) const override {
        return m_base ? m_base->palette(role) : QPlatformTheme::palette(role);
    }
    const QFont *font(Font role = SystemFont) const override {
        return m_base ? m_base->font(role) : QPlatformTheme::font(role);
    }
    QVariant themeHint(ThemeHint hint) const override {
        return m_base ? m_base->themeHint(hint) : QPlatformTheme::themeHint(hint);
    }
    bool usePlatformNativeDialog(DialogType type) const override {
        return m_base ? m_base->usePlatformNativeDialog(type) : QPlatformTheme::usePlatformNativeDialog(type);
    }
    QPlatformDialogHelper *createPlatformDialogHelper(DialogType type) const override {
        return m_base ? m_base->createPlatformDialogHelper(type) : QPlatformTheme::createPlatformDialogHelper(type);
    }
    QIconEngine *createIconEngine(const QString &name) const override {
        return m_base ? m_base->createIconEngine(name) : QPlatformTheme::createIconEngine(name);
    }
};
class HicsThemePlugin final : public QPlatformThemePlugin {
    Q_OBJECT
    Q_PLUGIN_METADATA(IID "org.qt-project.Qt.QPA.QPlatformThemeFactoryInterface.5.1" FILE "theme.json")
public:
    QPlatformTheme *create(const QString &key, const QStringList &) override {
        const auto version = QLibraryInfo::version();
        if (version.majorVersion() != QT_VERSION_MAJOR || version.minorVersion() != QT_VERSION_MINOR)
            return nullptr;
        return key == QLatin1String("hics") ? new HicsTheme : nullptr;
    }
};
#include "main.moc"
