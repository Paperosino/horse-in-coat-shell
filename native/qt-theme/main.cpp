#include <qpa/qplatformtheme.h>
#include <qpa/qplatformthemeplugin.h>
#include <qpa/qplatformthemefactory_p.h>
#include <QPalette>
#include <QIcon>
#include <QLibraryInfo>
#include <QVersionNumber>
#include <memory>
#include <QDir>
#include <QGuiApplication>
#include <unistd.h>

// qt*ct supplies the exact shell palette and fonts, but does not implement
// QPlatformTheme::colorScheme. KDE and automatic editor themes need both.
class HicsTheme final : public QPlatformTheme {
    std::unique_ptr<QPlatformTheme> m_base;
    mutable std::unique_ptr<QPlatformTheme> m_dialogs;
    mutable bool m_dialogsAttempted = false;
    QPlatformTheme *fileDialogs() const {
        const auto backend = QGuiApplication::platformName();
        if (backend != QLatin1String("xcb") && !backend.startsWith(QLatin1String("wayland"))) return nullptr;
        // Construct only when requested: GTK initialization does not belong
        // in every Qt application's startup or in palette-only consumers.
        if (!m_dialogsAttempted) {
            m_dialogsAttempted = true;
            m_dialogs.reset(QPlatformThemeFactory::create(QStringLiteral("gtk3")));
        }
        return m_dialogs.get();
    }
public:
    HicsTheme() : m_base(QPlatformThemeFactory::create(
#if QT_VERSION >= QT_VERSION_CHECK(6, 0, 0)
        QStringLiteral("qt6ct")
#else
        QStringLiteral("qt5ct")
#endif
    )) {
        if (geteuid() == 0 && qEnvironmentVariableIsEmpty("QT_QUICK_CONTROLS_CONF"))
            qputenv("QT_QUICK_CONTROLS_CONF", (QDir::homePath() + QStringLiteral("/.config/hics/qtquickcontrols2.conf")).toUtf8());
    }
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
        if (type == FileDialog)
            if (auto *dialogs = fileDialogs(); dialogs && dialogs->usePlatformNativeDialog(type)) return true;
        return m_base ? m_base->usePlatformNativeDialog(type) : QPlatformTheme::usePlatformNativeDialog(type);
    }
    QPlatformDialogHelper *createPlatformDialogHelper(DialogType type) const override {
        if (type == FileDialog)
            if (auto *dialogs = fileDialogs(); dialogs && dialogs->usePlatformNativeDialog(type))
                if (auto *helper = dialogs->createPlatformDialogHelper(type)) return helper;
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
        // Polkit clears QT_QPA_PLATFORMTHEME. Unix Qt still asks for generic;
        // intercept that fallback only for root, preserving ordinary sessions.
        return (key == QLatin1String("hics") || (key == QLatin1String("generic") && geteuid() == 0)) ? new HicsTheme : nullptr;
    }
};
#include "main.moc"
