# Расширения Hyprstack

Менеджер доступен в настройках → «Плагины». Установка поддерживает локальную папку,
ZIP, HTTPS ZIP и ссылку на каталог плагина GitHub. Новый плагин выключен до явного
включения. Обновление сохраняет резервную копию; доступны откат, удаление и восстановление.
QML-плагин выполняется с правами пользователя: устанавливайте код из доверенных источников.

## Форматы

| Формат | Поддержка |
| --- | --- |
| Hyprstack `api: "hyprstack-1"` | Основной формат: main, barWidget, desktopWidget, settings, panel |
| Noctalia QML, manifest.json | Частичный мост Commons/Services/Widgets; предварительная проверка импортов |
| AngelOS QML | Импорт манифеста; компоненты, зависящие от Skin/qs.config, требуют переноса |
| Noctalia 5 Luau, plugin.toml | Распознавание метаданных; выполнение Luau пока не реализовано |
| Noctalia W Engine | Нативный аналог в разделе живых обоев; выполнение Luau не требуется |

Это не полная замена среды Noctalia. Неподдерживаемые зависимости и API показываются
в менеджере. В Qt 6 используйте `import qs.Commons as Commons` и `Commons.Color.mPrimary`,
чтобы избежать конфликта с одноимёнными типами Qt.

Пользовательские расширения: `$XDG_DATA_HOME/hyprstack/plugins` (по умолчанию
`~/.local/share/hyprstack/plugins`). Настройки: `~/.config/hyprstack/plugins.json`.
Готовые примеры находятся в `shell/plugins`: pomodoro, system-monitor, web-search,
quick-actions, night-light. Последнему требуется `hyprsunset`.

## Минимальный плагин

`manifest.json`:

```json
{"id":"hello","name":"Hello","version":"1.0.0","api":"hyprstack-1","entryPoints":{"barWidget":"Bar.qml"},"settingsSchema":[{"key":"label","type":"string","default":"Hello"}]}
```

`Bar.qml`:

```qml
import QtQuick
import qs.components
Item {
    required property var pluginApi
    implicitWidth: label.implicitWidth
    implicitHeight: 28
    StyledText { id: label; anchors.centerIn: parent; text: pluginApi.pluginSettings.label }
}
```

API предоставляет `pluginId`, `pluginDir`, `pluginDataDir`, `pluginSettings`,
`mainInstance`, `saveSettings(value)`, `setSetting(key,value)`, `openPanel()`.
Точка входа может запросить `required property ShellScreen screen`.
Схема настроек поддерживает bool, int, number, string, choice и json.
Перетаскиваемые настольные виджеты сохраняют координаты через API настроек.

IPC: `hyprstack-shell ipc call plugins list`, `plugins refresh`,
`plugins enable ID`, `plugins disable ID`, `plugins reload`.
