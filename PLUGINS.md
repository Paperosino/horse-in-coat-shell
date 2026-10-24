# Расширения hics

Менеджер доступен в настройках → «Плагины». Установка поддерживает локальную папку,
ZIP, HTTPS ZIP и ссылку на каталог плагина GitHub. Новый плагин выключен до явного
включения. Обновление сохраняет резервную копию; доступны откат, удаление и восстановление.
QML-плагин выполняется с правами пользователя: устанавливайте код из доверенных источников.

## Форматы

| Формат | Поддержка |
| --- | --- |
| hics `api: "hics-1"` | Основной формат: main, barWidget, desktopWidget, settings, panel |
| Noctalia QML, manifest.json | Частичный мост Commons/Services/Widgets; предварительная проверка импортов |
| AngelOS QML | Импорт манифеста; компоненты, зависящие от Skin/qs.config, требуют переноса |
| Noctalia 5 Luau, plugin.toml | Распознавание метаданных; выполнение Luau пока не реализовано |
| Noctalia W Engine | Нативный аналог в разделе живых обоев; выполнение Luau не требуется |

Это не полная замена среды Noctalia. Неподдерживаемые зависимости и API показываются
в менеджере. В Qt 6 используйте `import qs.Commons as Commons` и `Commons.Color.mPrimary`,
чтобы избежать конфликта с одноимёнными типами Qt.

Пользовательские расширения: `$XDG_DATA_HOME/hics/plugins` (по умолчанию
`~/.local/share/hics/plugins`). Настройки: `~/.config/hics/plugins.json`.
Готовые примеры находятся в `shell/plugins`: pomodoro, system-monitor, web-search,
quick-actions, night-light. Последнему требуется `hyprsunset`.

## Минимальный плагин

`manifest.json`:

```json
{"id":"hello","name":"Hello","version":"1.0.0","api":"hics-1","entryPoints":{"barWidget":"Bar.qml"},"settingsSchema":[{"key":"label","type":"string","default":"Hello"}]}
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

IPC: `hics-shell ipc call plugins list`, `plugins refresh`,
`plugins enable ID`, `plugins disable ID`, `plugins reload`.

## Изолированные расширения hics-2

`api: "hics-2"` запускает Python worker в отдельном процессе bubblewrap.
В оболочку передаются декларативные элементы, а не QML или JavaScript.
Пример: `shell/plugins/isolated-counter`.

```json
{"id":"counter","api":"hics-2","worker":"worker.py","entryPoints":{"desktopWidget":"declarative","barWidget":"declarative"},"permissions":{"network":false}}
```

Протокол — JSON по одной строке. Первое входное сообщение:
`{"type":"init","settings":{}}`. Нажатие передаётся как
`{"type":"action","id":"increment","value":null}`. Worker публикует полное состояние:

```json
{"slots":{"desktopWidget":[{"type":"heading","text":"Счётчик"},{"type":"button","text":"Добавить","id":"increment","icon":"add"}]}}
```

Доступны `label`, `heading`, `button`, `toggle` с логическим `value`, `progress`
с числом 0–1. Разрешены только текст, имя иконки, идентификатор действия,
значение и `enabled`. Максимум 32 элемента на слот, один элемент на панели,
64 КиБ на сообщение и 20 обновлений в секунду. Начальное состояние необходимо
опубликовать за 10 секунд. Превышение лимита или авария отключает расширение
и сохраняет причину в журнале.

Песочница видит `/usr` и собственный каталог `/plugin` только для чтения,
личный `/data` для записи; домашний каталог, Wayland и D-Bus не передаются.
Сеть по умолчанию изолирована. Даже если манифест запрашивает сеть, её требуется
разрешить в настройках расширения; изменение разрешения перезапускает worker.
Ограничения процесса: 512 МиБ адресного пространства, 60 секунд суммарного CPU,
64 дескриптора и 16 МиБ на файл. Изоляция зависит от поддержки непривилегированных
пользовательских пространств имён ядром; при недоступности запускается ошибка,
а не незащищённый процесс. Старые hics-1 и сторонние QML остаются доверенным кодом.

После аварийного завершения оболочка запускает расширения в восстановительном
режиме: их можно включать по одному либо возобновить все. Обычный перезапуск
не включает этот режим. Последние 50 ошибок каждого расширения сохраняются.

## Каталог

Страница расширений показывает встроенные примеры и принимает HTTPS JSON-каталог:

```json
{"version":1,"extensions":[{"id":"counter","name":"Счётчик","version":"1.0","description":"Описание","source":"https://example.org/counter.zip","preview":"https://example.org/counter.png","dependencies":["python"]}]}
```

Ссылки установки и предпросмотра требуют HTTPS. Каталог ограничен 2 МиБ и
1000 записями; установка не включает код автоматически. Зависимости манифеста
проверяются перед включением, а установка пакетов ОС остаётся явным действием.
Центральный сервер каталога не требуется: можно использовать собственный.

## Виджеты рабочего стола

Включите редактирование в настройках расширений. Перетаскивание меняет положение,
угол — размер; стрелки перемещают, Ctrl + стрелки меняют размер. Доступны
закрепление, привязка к сетке, сброс размера и кнопка завершения редактирования.
Кнопка сетки переключает шаг 16 → 32 → 8. Геометрия хранится по имени монитора
в `plugins.json → desktopLayout`, отдельно от настроек самого расширения.
