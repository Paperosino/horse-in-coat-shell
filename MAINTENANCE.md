[На главную](README.md) · [Установка](INSTALL.md)

# Обновление и восстановление

## Обновление

### Arch Linux и производные

Завершите Hyprland, войдите в TTY (**Ctrl+Alt+F3**) и выполните без `sudo`:

```bash
cd /путь/к/hyprstack-shell
./update.sh
```

Скрипт получает исходники, проверяет ABI, собирает проект и обновляет файлы
с резервной копией. Личные Lua/JSON-настройки и тема сохраняются.
Если `update.sh` ещё нет в старом клоне, сначала выполните `git pull --ff-only`.

Опции: `--dry-run` — план изменений, `--jobs 1` — сборка с меньшим расходом памяти,
`--no-pull` — сборка текущих исходников. Свои изменения в Git сохраните
коммитом или через `git stash`.

После обновления войдите в Hyprland и выполните `hyprstack-doctor`.
Для отката снова завершите сеанс и запустите:

```bash
./update.sh --rollback
```

Копии: `${XDG_STATE_HOME:-$HOME/.local/state}/hyprstack-install/backups/`.
Откат не меняет системные пакеты; требуется Hyprland **0.56.2**.
Для конфигурации со ссылками на каталоги используйте свой менеджер dotfiles.

**Для установки пакетом** (`packaging/arch/build-package.sh`) обновление
выполняется повторным запуском того же сценария: пакет пересобирает
вложенный рантайм Quickshell/Qt под текущую системную Qt и упаковывает
его заново. Сценарий `update.sh` выше предназначен для установок
в `$HOME/.local` и для пакетной установки не используется.

### NixOS и Home Manager

Из каталога конфигурации NixOS, заменив `YOUR_HOST`:

```bash
nix flake update hyprstack
sudo nixos-rebuild switch --flake .#YOUR_HOST
```

Войдите в новый сеанс. Встроенный Home Manager применится вместе с системой.
Для отдельного Home Manager обновите тот же вход в его flake и выполните
`home-manager switch --flake .#YOUR_USER`. `update.sh` на NixOS не используется.

Без Home Manager обновите пользовательскую конфигурацию по
[инструкции](INSTALL.md#config), затем верните личные Lua/JSON-файлы из копии.
Сборку CMake и копирование службы пропустите.

## Диагностика

```bash
hyprstack-doctor
hyprctl configerrors
hyprstack-doctor --json
journalctl --user -u hyprstack-session.service -b
```

Для запуска оболочки с выводом ошибок в терминал:

```bash
hyprstack-session stop
hyprstack-shell
```

- **QML:** проверьте совместимость Qt/Quickshell и наличие модулей `horse-in-coat-shell`
  и `M3Shapes`. После обновления Qt пересоберите horse-in-coat-shell и, если нужно, Quickshell.
- **PAM:** проверьте пакет `hyprlock` и `/etc/pam.d/hyprlock`.
- **Polkit:** остановите сторонний агент авторизации.
- **Вложенный рантайм:** при установке пакетом Quickshell и Qt берутся из
  `/usr/share/hyprstack/qs`; проверка версии:
  `LD_LIBRARY_PATH=/usr/share/hyprstack/qs/lib /usr/share/hyprstack/qs/bin/hyprstack-qs --version`.

Перезапуск оболочки: `hyprstack-session restart`.

## Восстановление прежнего окружения

На NixOS верните предыдущую ревизию конфигурации и примените её либо загрузите
прежнее поколение системы. Восстановите также конфигурацию Home Manager.
Изменяемые настройки пользователя возвращаются из резервной копии отдельно.

Без Home Manager завершите Hyprland и перейдите в TTY:

1. Найдите `hyprstack-backup.*`, выведенный при установке.
2. Перенесите нынешние `hypr` и `hyprstack` из `${XDG_CONFIG_HOME:-$HOME/.config}`
   в отдельный каталог и верните туда прежние каталоги или ссылки из копии.
3. Верните сохранённый `hyprstack-session.service` в `systemd/user/`.
   Если прежней службы не было, удалите только установленную службу horse-in-coat-shell.
4. При наличии пользовательского systemd выполните `systemctl --user daemon-reload`
   и войдите в прежнее окружение.

## Удаление

На NixOS отключите `programs.hyprstack.enable` в системной конфигурации
и Home Manager, удалите ненужные импорты и вход `hyprstack`, примените изменения.

На Arch-based системах восстановите прежнюю конфигурацию по разделу выше.
Установленные CMake файлы перечислены в `build/install_manifest.txt` вашей сборки;
просмотрите список и удалите указанные файлы horse-in-coat-shell.

Пользовательские данные удаляются по желанию:

| Каталог | Содержимое |
| --- | --- |
| `${XDG_CONFIG_HOME:-$HOME/.config}/hyprstack` | Настройки |
| `${XDG_STATE_HOME:-$HOME/.local/state}/hyprstack` | Тема, обои, история и состояние |
| `${XDG_CACHE_HOME:-$HOME/.cache}/hyprstack` | Кеш изображений |

## Проверка четырёх режимов

Нативный холст закреплён через `third_party/phantomat/UPSTREAM_REVISION`.
При обновлении сначала собирайте его против используемого ABI Hyprland и
проверяйте переходы tiling → stacking → scrolling → canvas → scrolling
в отдельном вложенном compositor-сеансе. Одновременно патчить drawTex двумя
обзорами нельзя: `overview_hooks(false)` передаёт рендер холсту,
`spatialoverview.hyprstack_close()` освобождает его перед возвратом.
Не удаляйте синхронную функцию без замены протокола передачи рендера.

После сборки `python tests/integration_canvas.py --pointer` запускает отдельный
Wayland-сеанс с изолированными настройками и состоянием. Проверяет отсутствие
заголовков и миграции в стакинг, реальные значения масштаба, Ctrl+колесо и
перемещение камеры средней кнопкой через `/dev/uinput`, перезагрузку конфигурации
и восстановление плавающих/тайловых окон при выходе. Без `--pointer` проверка
не создаёт виртуальное устройство ввода. Скрипт закрывает только свои окна.

## Системный D-Bus backend

`native/system`: C++-демон `hyprstack-systemd` и клиент `hyprstack-systemctl`.
API `org.hyprstack.System1` (`/org/hyprstack/System1`): `Status(section)` и
`Apply(section, operation, json)`, JSON-ответы с кодами ошибок. Разделы: printers,
storage, datetime, power; printer-discovery выполняет ограниченный поиск CUPS.

Демон выводит UID из уникального имени D-Bus-отправителя. Операции разрешены
по спискам и проверяются до авторизации; административные изменения используют
Polkit. Команды оболочки, пути программ, пароли и UID из запроса не принимаются.
Задания печати фильтруются по имени пользователя; чужое задание отменить нельзя.
До 4 рабочих потоков, 16 ожидающих запросов, ограничение входного JSON и таймауты.
Монтирование/отключение делает нативный клиент от своего UID непосредственно
через UDisks2: запуск от root потерял бы пользователя и его каталог монтирования.

Проверки: `python -m unittest discover -s tests`; после сборки
`hyprstack-systemctl status printers`, `storage`, `datetime`, `power`.
Изменения параметров ОС не выполняются при чтении и открытии страницы.
Поддержка печати использует libcups/IPP, времени — timedate1, питания —
PowerProfiles, дисков — UDisks2; настройки приложения settings-ui использованы
как ориентир по возможностям, без копирования его Python/sudo backend.
