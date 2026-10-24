# Сторонние компоненты и лицензии

horse-in-coat-shell 1.1.1 включает изменённый код перечисленных проектов. Интерфейс и
имена компонентов используют horse-in-coat-shell; исходные названия ниже сохраняют
указание авторства. Дата изменений: 10.10.2026.

| Компонент | Источник | Лицензия | Локальный файл лицензии |
| --- | --- | --- | --- |
| Оболочка и нативные модули QML, на основе Caelestia shell 2.5.0 | https://github.com/caelestia-dots/shell | GPL-3.0 | `shell/LICENSE` |
| Нативные декорации окон, изменённый hyprbars | https://github.com/hyprwm/hyprland-plugins/tree/7644cecdb947060682891a0db2a0cdc5c0b9e704/hyprbars | BSD-3-Clause | `native/hyprbars/LICENSE` |
| M3Shapes, коммит `8a6fe8961749887d677700b6508e0c9249968b7e` | https://github.com/soramanew/m3shapes | Apache-2.0 | `third_party/m3shapes/LICENSE` |
| Google Sans Flex | https://github.com/googlefonts/google-sans-flex | SIL OFL-1.1 | `shell/assets/google-sans-flex/LICENSE` |
| Material Symbols Rounded | https://github.com/google/material-design-icons | Apache-2.0 | `shell/assets/material-symbols/LICENSE` |

Исходники включённых нативных библиотек предоставляются в этой поставке.
Изменения включают оформление и названия horse-in-coat-shell, команды управления рабочим
столом, запуск и завершение сеанса, стандартную конфигурацию, размещение окон и
обзор, историю уведомлений, цветовые темы, кэширование изображений, управление
ресурсами и русский перевод с переключением языка.

Логотип в `shell/assets/logo.svg` и `shell/components/Logo.qml` — собственный
дизайн под лицензией проекта. Шрифты сохраняют свои отдельные лицензии.
Зависимости из репозиториев дистрибутива остаются отдельными проектами
со своими лицензиями.

Встроенные палитры сохраняют исходные значения RGB и названия цветов.
Проекты-источники и адаптации режимов перечислены в
[источниках палитр](shell/assets/schemes/SOURCES.md).

Кадры и короткая запись интерфейса находятся в `docs/media/` и не устанавливаются
вместе с оболочкой. Сведения об изображениях, видимых в записи, приведены в
[описании демонстрации](docs/media/README.md).

## Вложенный рантайм пакета

Пакет `runhics-shell` (см. `packaging/arch/`) дополнительно включает
собранные из исходников бинарные компоненты со своими лицензиями:

| Компонент | Источник | Лицензия | Локальный файл лицензии |
| --- | --- | --- | --- |
| Quickshell v0.3.2 | https://github.com/quickshell-mirror/quickshell | LGPL-3.0 | `/usr/share/hyprstack/qs/licenses/quickshell-LGPL-3.0` |
| Библиотеки Qt 6 | https://www.qt.io | LGPL-3.0 | `/usr/share/hyprstack/qs/licenses/qt/` |

Вложение выполняется при сборке пакета; лицензии устанавливаются вместе
с пакетом. Для установок без пакета (CMake в `$HOME/.local`) системные
Quickshell и Qt используются как раньше и не вкладываются.

## Desktop feature ports

- AngelOS Dotfiles, MixaDoDs, MIT, commit `8011b206e71e7c57ce31d6fe769eb710fab9904c`: palette colors from `config/Theme.qml` and the web-search engine catalog are adapted into horse-in-coat-shell's M3 palette and native search extension. The MIT notice is installed as `licenses/AngelOS-MIT`. Plugin lifecycle, settings, and wallpaper concepts informed independent native implementations. Source: https://github.com/MixaDoDs/AngelOS-Dotfiles
- Noctalia community W Engine, TadomiKa-Ari, MIT, commit `daa4a2f5e2aca664c2f4f2b71d3e42112e698839`: documented engine options, Workshop discovery and manifest semantics informed a native adapter. Luau plugin code is not executed or redistributed as a compatible runtime. Source: https://github.com/noctalia-dev/community-plugins/tree/main/w-engine
- hyprland-dots-userfriendly/settings-ui: used as a feature reference for input, compositor controls, autostart, and user units. Its Python/PySide implementations were not copied; horse-in-coat-shell uses typed Lua settings and its own QML controls.

- Phantomat / Spatial Overview, Zsolt Kacso and upstream Hypr Development, BSD-3-Clause, pinned commit `a1e8a0806541640d01503ac861a8a39548de8724`: vendored in `third_party/phantomat`. horse-in-coat-shell adds a synchronous renderer handoff function, builds against the same Hyprland ABI, and supplies its own mode/configuration UI. License installed as `licenses/Phantomat-BSD-3-Clause`. Source: https://github.com/kaolti/phantomat

Phantomat integration also enables Ctrl-wheel/pinch from the resting canvas,
preserves wheel input over shell layer surfaces, and adds a camera zoom reset action.
Its native-layout snapshot is used directly, without the shell stacking migration.

The canvas regression tests include the MIT-licensed `wlr-virtual-pointer-unstable-v1.xml` from [wlr-protocols](https://github.com/swaywm/wlr-protocols). The protocol retains its upstream copyright and license notice.

### First-launch guide references and recordings

The optional onboarding flow was informed by
[AngelOS-Dotfiles](https://github.com/MixaDoDs/AngelOS-Dotfiles). The hics guide
uses hics components, services and original implementation.

The recorded tour includes the GNOME Backgrounds artwork **Glass Chip (dark)**,
© Jakub Steiner, 2024, under
[CC BY-SA 3.0 US](https://creativecommons.org/licenses/by-sa/3.0/us/).
Source: [gnome-backgrounds](https://github.com/GNOME/gnome-backgrounds/tree/76ad782dd3afd1e16b14022872a3aa9561577355).
The artwork is visible behind the recorded shell and applications; the
wallpaper-containing GIF and MP4 recordings are distributed under the same CC BY-SA
license. Shell source code retains its own license. Recordings were resized and
palette-quantized, and are real screen captures rather than rendered mockups.

The optional wallpaper collection uses the same pinned GNOME Backgrounds source.
Original files, embedded individual artist metadata and license information are
retained with downloaded images; JPEG files are format conversions.
