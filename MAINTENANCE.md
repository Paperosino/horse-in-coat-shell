[На главную](README.md) · [Установка](INSTALL.md)

# Обновление и восстановление

## Обновление

Нативный модуль зависит от ABI Hyprland. После обновления композитора нужна
пересборка под соответствующие заголовки. Исходники 1.1.1 рассчитаны на
**Hyprland 0.56.2**; для другой версии нужен совместимый выпуск Hyprstack.
Готовый модуль с другого компьютера не заменяет сборку.

### Arch-based: обновление из Git или ZIP

Команды рассчитаны на установку из [INSTALL.md](INSTALL.md) в `~/.local`.
Выполняйте их обычным пользователем в Bash, в одном терминале. После ошибки
устраните причину, прежде чем выполнять следующую команду.

**Завершите Hyprland и перейдите в TTY до установки файлов.** Перезапуск одной
оболочки не обновляет уже загруженный в композитор нативный модуль.

1. Перейдите в каталог исходников и сохраните конфигурацию:

   ```bash
   cd /путь/к/hyprstack-shell
   config_dir=${XDG_CONFIG_HOME:-$HOME/.config}
   backup_dir=$(mktemp -d "$HOME/hyprstack-backup.XXXXXXXX")

   for name in hypr hyprstack; do
       if [ -e "$config_dir/$name" ] || [ -L "$config_dir/$name" ]; then
           cp -a "$config_dir/$name" "$backup_dir/$name"
       fi
   done

   if [ -e "$config_dir/systemd/user/hyprstack-session.service" ] || \
      [ -L "$config_dir/systemd/user/hyprstack-session.service" ]; then
       cp -a "$config_dir/systemd/user/hyprstack-session.service" "$backup_dir/"
   fi
   printf 'Резервная копия: %s\n' "$backup_dir"
   ```

   Запишите выведенный путь. При собственных XDG-переменных используйте те же
   значения, что и в графическом сеансе. Личные изменения управляемых файлов
   `hypr/` и `hyprstack/hypr-user.lua` предварительно перенесите в
   `hyprstack/local.lua`, `monitors.lua` или `hypr-vars.lua`.

2. Получите новые исходники. Для Git:

   ```bash
   git status --short
   git rev-parse HEAD > "$backup_dir/source-revision"
   git pull --ff-only
   ```

   Если есть собственные изменения исходников, сначала сохраните их отдельным
   коммитом или через `git stash`. Для ZIP скачайте новый архив, распакуйте в
   отдельный каталог и перейдите в него; команды Git пропустите.

3. Сверьте зависимости с новым [INSTALL.md](INSTALL.md), затем соберите
   проект в новом каталоге. Проверка ABI выполняется при настройке CMake:

   ```bash
   Hyprland --version-json
   qs --version
   pkg-config --modversion Qt6Core hyprland

   build_dir=$(mktemp -d "$PWD/build-update.XXXXXXXX")
   cmake -S . -B "$build_dir" -G Ninja \
     -DCMAKE_BUILD_TYPE=Release \
     -DCMAKE_INSTALL_PREFIX="$HOME/.local" \
     -DCMAKE_INSTALL_DATADIR="${XDG_DATA_HOME:-$HOME/.local/share}"
   cmake --build "$build_dir" --parallel 2
   cmake --install "$build_dir"
   printf '%s\n' "$build_dir" > "$backup_dir/build-directory"
   ```

   При недостатке памяти используйте `--parallel 1`. Сохраните каталог сборки:
   в нём находится `install_manifest.txt` для последующего ручного удаления.

4. Обновите управляемую Lua-конфигурацию. Это необходимо и для новых жестов:
   `cmake --install` сам по себе не обновляет `~/.config/hypr`.

   ```bash
   next_hypr=$(mktemp -d "$config_dir/hyprstack-update.XXXXXXXX")
   cp -R shell/assets/hyprland/config/. "$next_hypr/"
   if [ -f "$config_dir/hypr/scheme/current.lua" ]; then
       cp -L "$config_dir/hypr/scheme/current.lua" "$next_hypr/scheme/current.lua"
   fi
   if [ -e "$config_dir/hypr" ] || [ -L "$config_dir/hypr" ]; then
       mv "$config_dir/hypr" "$backup_dir/hypr-replaced"
   fi
   mv "$next_hypr" "$config_dir/hypr"

   mkdir -p "$config_dir/hyprstack" "$config_dir/systemd/user"
   cp --remove-destination distribution/defaults/hyprstack/hypr-user.lua "$config_dir/hyprstack/"
   cp --remove-destination distribution/systemd/user/hyprstack-session.service "$config_dir/systemd/user/"
   ```

   `hypr-vars.lua`, `monitors.lua`, `local.lua`, JSON-настройки, тема и данные
   пользователя сохраняются. Не копируйте весь каталог стандартных настроек
   `distribution/defaults/hyprstack/` поверх существующего при обновлении.
   Корневая ссылка `hypr`, если она была, переносится целиком: исходники вашего
   менеджера dotfiles не перезаписываются.

5. Если используется пользовательский systemd, выполните в TTY:

   ```bash
   if command -v systemctl >/dev/null 2>&1 && systemctl --user show-environment >/dev/null 2>&1; then
       systemctl --user daemon-reload
   fi
   ```

   Войдите в новый сеанс Hyprland и проверьте результат:

   ```bash
   hyprstack-doctor
   hyprctl configerrors
   ```

   Список ошибок конфигурации должен быть пустым. Не удаляйте резервную копию
   до проверки настроек и приложений. Для возврата к прежнему выпуску восстановите
   его исходники (Git-ревизия сохранена в `source-revision`), пересоберите их под
   совместимый Hyprland и верните конфигурацию из резервной копии.

### NixOS и Home Manager

В каталоге **своей конфигурации NixOS** обновите только вход Hyprstack и
примените конфигурацию, заменив `YOUR_HOST` своим именем системы:

```bash
nix flake update hyprstack
sudo nixos-rebuild switch --flake .#YOUR_HOST
```

Home Manager, встроенный в конфигурацию NixOS, применится вместе с системой.
Если он используется отдельно, обновите вход `hyprstack` также в его flake
и выполните `home-manager switch --flake .#YOUR_USER`. Пакет Hyprstack,
Hyprland и Quickshell должны оставаться из одного совместимого набора.

Завершите старый сеанс и войдите заново. При использовании Home Manager
управляемая Lua-конфигурация обновится автоматически; не копируйте файлы
поверх его ссылок. Без Home Manager обновите `hypr/` и `hypr-user.lua` по шагу 4
выше, используя конфигурацию из нового пакета
`$HYPRSTACK_DATA_DIR/shell/assets/hyprland/config/` и
`$HYPRSTACK_DATA_DIR/defaults/hyprstack/hypr-user.lua`. Сначала сохраните
резервную копию по шагу 1. Службу systemd предоставляет модуль NixOS,
копировать её и выполнять CMake на NixOS не требуется.

После входа выполните `hyprstack-doctor` и `hyprctl configerrors`.

## Диагностика

```bash
hyprstack-doctor
hyprctl configerrors
hyprstack-doctor --json
```

Для установки с пользовательским systemd:

```bash
journalctl --user -u hyprstack-session.service -b
```

Если оболочка не запускается, остановите сеанс оболочки и запустите её в
терминале, чтобы прочитать сообщение:

```bash
hyprstack-session stop
hyprstack-shell
```

При ошибке импорта QML проверьте совместимость Qt и Quickshell, модули
`Hyprstack` и `M3Shapes` в `${XDG_DATA_HOME:-$HOME/.local/share}/hyprstack/qml`
и наличие пакетов QML из инструкции установки. После обновления Qt пересоберите
Hyprstack; Quickshell, собранный вручную, также может требовать пересборки.

При ошибке PAM проверьте наличие системного `/etc/pam.d/hyprlock` и пакет
`hyprlock`. При ошибке регистрации Polkit остановите другой агент авторизации.

## Восстановление прежнего окружения

На NixOS восстановите предыдущую ревизию своей системной конфигурации и
примените её через `nixos-rebuild switch` либо выберите прежнее поколение NixOS
при загрузке. Если используется Home Manager, восстановите и его конфигурацию.
Изменяемые JSON/Lua-настройки пользователя восстанавливаются из вашей резервной
копии отдельно от поколений Nix. Следующие действия с каталогами относятся к
установке без Home Manager.

Завершите Hyprland и перейдите в TTY. Найдите каталог `hyprstack-backup.*`,
который был выведен при установке. В нём находятся исходные каталоги
`hypr`, `hyprstack` и, если существовал, `hyprstack-session.service`.

Сначала перенесите нынешние `hypr` и `hyprstack` в отдельный каталог, чтобы
сохранить сделанные после установки изменения. Затем верните исходные каталоги
или ссылки из резервной копии на их прежние места в `$XDG_CONFIG_HOME`
(по умолчанию `~/.config`). Если какого-либо каталога до установки не было,
восстанавливать его не нужно.

Верните прежний `systemd/user/hyprstack-session.service`, если он был сохранён.
В противном случае удалите только службу, скопированную при установке Hyprstack.
При наличии пользовательского systemd выполните `systemctl --user daemon-reload`.
После этого входите в прежнее рабочее окружение.

## Ручное удаление файлов программы

На NixOS отключите `programs.hyprstack.enable` в системной конфигурации и,
если он используется, в Home Manager, затем примените конфигурации. Уберите
импорты модулей и вход `hyprstack`, если они больше не нужны. Восстановите прежнюю
пользовательскую конфигурацию из резервной копии. Файлы в `/nix/store` вручную
не удаляют. Команды по манифесту CMake ниже относятся к Arch-based установке.

Сначала восстановите конфигурацию по предыдущему разделу. Список файлов,
размещённых CMake, хранится в `build/install_manifest.txt` именно вашей сборки.
Просмотрите его и удаляйте только перечисленные файлы Hyprstack.
Не удаляйте `~/.local/bin`, `~/.local/share` или каталоги других приложений целиком.

Пользовательские данные хранятся отдельно:

| Каталог | Содержимое |
| --- | --- |
| `${XDG_CONFIG_HOME:-$HOME/.config}/hyprstack` | Настройки |
| `${XDG_STATE_HOME:-$HOME/.local/state}/hyprstack` | Текущая тема, путь к обоям, история и состояние |
| `${XDG_CACHE_HOME:-$HOME/.cache}/hyprstack` | Кеш изображений |

Удаление этих каталогов необязательно. Системные зависимости удаляются отдельно
через пакетный менеджер; сначала проверьте, нужны ли они другим приложениям.
