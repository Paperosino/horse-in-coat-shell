[English](INSTALL.en.md) · [На главную](README.md)

# Установка Hyprstack

Выполняйте шаги по порядку, под обычным пользователем. `sudo` используется только
для установки системных пакетов. Команды ниже рассчитаны на Bash. Если команда
завершилась ошибкой, устраните её до перехода к следующему шагу.

## 1. Проверьте совместимость

| Компонент | Требуется |
| --- | --- |
| Hyprland | **0.56.2**, с Lua-конфигурацией |
| Заголовки Hyprland | Из той же сборки, с тем же ABI, что установленный композитор |
| Quickshell | **≥ 0.3.1**, включая Hyprland, PAM, Polkit, PipeWire, Bluetooth, UPower, уведомления и трей |
| Qt | **≥ 6.9**, общая совместимая сборка для Quickshell и модулей Hyprstack |
| Компилятор | C++23, например GCC ≥ 14 |
| Инструменты | CMake ≥ 3.22, Ninja, pkg-config, gettext, Python ≥ 3.10, Pillow |

Установленный и запущенный Hyprland должны совпадать. Если композитор обновлён,
сначала завершите старый сеанс. После изменения его ABI пересоберите нативный
модуль. Для версии Hyprland, отличной от 0.56.2, нужен совместимый выпуск Hyprstack.

Поддерживаемые семейства: **Arch Linux и основанные на нём дистрибутивы**,
а также **NixOS**. Сборка и графические проверки на рабочем окружении выполнены
на CachyOS; NixOS использует отдельный пакет и модули конфигурации. Fedora,
Debian/Ubuntu и openSUSE в поддерживаемые платформы не входят. Не смешивайте
пакеты разных выпусков ради одного компонента.

## 2. Установите зависимости своего дистрибутива

Для сборки нужны Qt Core, Gui, Qml, Quick, QuickControls2, Concurrent, Sql,
Network, DBus и ShaderTools, приватные заголовки Qt Quick, libqalculate, libsensors,
заголовки Hyprland, pixman, libdrm, libinput, libudev, Wayland, xkbcommon и
Pango/Cairo. M3Shapes, шрифты и Material Symbols уже включены в исходники.

На Arch-based системах сначала проверьте версии пакетов в своей ветке. **Команды установки Hyprland
ниже применимы только при наличии версии 0.56.2.** Если её нет, подготовьте
совместимый стек для своей системы по [документации Hyprland](https://wiki.hypr.land/Getting-Started/Installation/)
и [Quickshell](https://quickshell.org/docs/v0.3.0/guide/install-setup/), затем
вернитесь к проверке в шаге 3. Hyprstack не добавляет сторонние репозитории.

<a id="arch"></a>

### Arch Linux / CachyOS / EndeavourOS / Manjaro

1. Посмотрите доступные версии:

   ```bash
   pacman -Si hyprland quickshell qt6-base
   ```

   В Manjaro учитывайте отставание выбранной ветки. Требования к версиям те же.

2. Если версии совместимы, установите стек и зависимости сборки полным
   обновлением системы:

   ```bash
   sudo pacman -Syu --needed base-devel git cmake ninja pkgconf gettext \
     hyprland quickshell nlohmann-json qt6-base qt6-declarative qt6-shadertools \
     qt6-svg qt6-imageformats qt6-wayland libqalculate lm_sensors \
     pixman libdrm libinput systemd-libs wayland libxkbcommon pango cairo \
     python python-pillow
   ```

3. Установите программы для функций оболочки:

   ```bash
   sudo pacman -S --needed kitty firefox fuzzel btop pavucontrol \
     wl-clipboard cliphist grim slurp wf-recorder swappy libnotify \
     brightnessctl networkmanager pipewire pipewire-pulse wireplumber \
     polkit hyprlock hyprpicker xdg-utils xdg-user-dirs libxml2 adwaita-icon-theme
   ```

4. Перейдите к шагу 3 ниже.

<a id="nixos"></a>

### NixOS

На NixOS используйте пакет этого репозитория: Hyprland, Quickshell и Qt берутся
из одного зафиксированного nixpkgs. Нативный модуль собирается с заголовками
того же Hyprland. Проверка ABI сохраняется и в Nix-сборке.

1. Добавьте вход в существующий `flake.nix` конфигурации NixOS:

   ```nix
   inputs.hyprstack.url = "github:hase9awa/hyprstack-shell";
   ```

2. В `outputs` передайте `hyprstack` и добавьте модуль в `modules` своей системы:

   ```nix
   outputs = { nixpkgs, hyprstack, ... }: {
     nixosConfigurations.YOUR_HOST = nixpkgs.lib.nixosSystem {
       modules = [
         ./configuration.nix
         hyprstack.nixosModules.default
         { programs.hyprstack.enable = true; }
       ];
     };
   };
   ```

   Сохраните остальные входы, модули и параметры своей конфигурации. Модуль
   включает совместимый Hyprland, PAM для hyprlock и пользовательскую службу
   оболочки. Настройки мониторов, видеодрайверов, дисков и оборудования он не
   задаёт. Не переопределяйте `programs.hyprland.package` другим пакетом:
   проверка модуля отклонит несовпадение.

3. Примените свою конфигурацию и войдите в новый сеанс:

   ```bash
   sudo nixos-rebuild switch --flake .#YOUR_HOST
   ```

   Сеть в оболочке использует NetworkManager, звук — PipeWire/WirePlumber.
   Включите нужные службы в своей конфигурации NixOS. Модуль не меняет выбранный
   вами способ управления сетью или звуком.

4. Разместите пользовательскую конфигурацию одним из способов:

   - **С Home Manager:** добавьте `hyprstack.homeManagerModules.default` в
     `imports` пользовательского модуля и включите `programs.hyprstack.enable`.
     Сначала сохраните существующие `~/.config/hypr` и
     `~/.config/hyprstack/hypr-user.lua`: Home Manager не заменяет конфликтующие
     файлы молча. Начальные настройки копируются только при отсутствии и
     остаются доступными для изменения из интерфейса.

     ```nix
     home-manager.users.YOUR_USER = {
       imports = [ hyprstack.homeManagerModules.default ];
       programs.hyprstack.enable = true;
     };
     ```

   - **Без Home Manager:** скачайте исходники и выполните команды резервного
     копирования и размещения файлов из шага 5 ниже. Сборка CMake и установка
     в `~/.local` не нужны — программы уже установлены модулем NixOS.

     ```bash
     git clone https://github.com/hase9awa/hyprstack-shell.git
     cd hyprstack-shell
     ```

5. Войдите в Hyprland и выполните `hyprstack-doctor` и `hyprctl configerrors`.
   При обновлении меняйте вход `hyprstack` в своей Nix-конфигурации, пересобирайте
   систему и входите в новый сеанс. Home Manager управляет своими файлами:
   не запускайте поверх них ручное копирование.

Шаги 3–4 ниже относятся к сборке на Arch-based системах. Для NixOS используйте
пакет и модули, описанные выше.

### Необязательные компоненты и системные службы

Сеть использует работающий NetworkManager; звук — PipeWire и WirePlumber.
Сохраняйте способ запуска служб, принятый в вашем дистрибутиве. Для сеанса также
нужны работающая пользовательская D-Bus и агент Polkit, встроенный в Quickshell.
Не запускайте одновременно второй агент Polkit или второй демон уведомлений.

`bluez` нужен для Bluetooth, `upower` — для информации о батарее,
`power-profiles-daemon` — для профилей питания, `ddcutil` — для яркости внешнего
монитора, `wtype` — для вставки выбранного emoji. Устанавливайте их при
необходимости, используя имена пакетов своего дистрибутива. Отсутствие внешнего
монитора, батареи или Bluetooth не должно требовать фиктивных устройств.

Графический файловый менеджер открывается через `xdg-open`; установите удобный
вам файловый менеджер. Firefox и kitty можно заменить в пользовательских
настройках. `grim`/`slurp`/`swappy` относятся к снимкам экрана,
`wf-recorder` — к записи, `hyprpicker` — к выбору цвета. Если дополнительный
пакет отсутствует в вашей ветке, соответствующая функция требует его отдельной
установки.

## 3. Проверьте готовый стек

```bash
Hyprland --version-json
qs --version
pkg-config --modversion Qt6Core hyprland
c++ --version
cmake --version
test -r /etc/pam.d/hyprlock
```

Hyprland должен сообщать `version: 0.56.2` и непустой `abiHash`, Quickshell —
версию от 0.3.1, Qt — от 6.9. Последняя команда проверяет системный PAM-сервис
блокировки; при ошибке сначала установите `hyprlock`. Не копируйте чужие
PAM-конфигурации в `/etc/pam.d`.

CMake дополнительно сравнит ABI заголовков с композитором и остановит сборку
при несовпадении. Если Quickshell собран без PAM или Polkit, пересоберите его
с этими модулями по инструкции Quickshell.

## 4. Получите исходники и соберите оболочку

Склонируйте репозиторий:

```bash
git clone https://github.com/hase9awa/hyprstack-shell.git
cd hyprstack-shell
```

Можно также скачать ZIP через **Code → Download ZIP**, распаковать его
и открыть терминал в каталоге с `CMakeLists.txt`. Дополнительные Git-подмодули не нужны.

```bash
cmake -S . -B build -G Ninja \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_INSTALL_PREFIX="$HOME/.local" \
  -DCMAKE_INSTALL_DATADIR="${XDG_DATA_HOME:-$HOME/.local/share}"
cmake --build build --parallel 2
cmake --install build
```

При небольшом объёме памяти используйте `--parallel 1`. Ни одну из этих команд
не запускайте через `sudo`. Звуковой визуализатор не входит в базовую сборку;
его дополнительные зависимости описаны в [CONFIGURATION.md](CONFIGURATION.md).

## 5. Сохраните конфигурацию и разместите файлы

**Завершите графический сеанс и выполняйте этот шаг из TTY.** Новая
Lua-конфигурация заменяет конфигурацию Hyprland; её части должны попасть на место
до следующего запуска композитора.

Снова перейдите в корень скачанных исходников. Сначала перенесите существующие
каталоги в уникальную резервную копию:

```bash
config_dir=${XDG_CONFIG_HOME:-$HOME/.config}
backup_dir=$(mktemp -d "$HOME/hyprstack-backup.XXXXXXXX")
mkdir -p "$config_dir/systemd/user"

for name in hypr hyprstack; do
    if [ -e "$config_dir/$name" ] || [ -L "$config_dir/$name" ]; then
        mv "$config_dir/$name" "$backup_dir/$name"
    fi
done

if [ -e "$config_dir/systemd/user/hyprstack-session.service" ] || \
   [ -L "$config_dir/systemd/user/hyprstack-session.service" ]; then
    mv "$config_dir/systemd/user/hyprstack-session.service" "$backup_dir/hyprstack-session.service"
fi

printf 'Резервная копия: %s\n' "$backup_dir"
```

Запишите выведенный путь. Символические ссылки переносятся как ссылки, поэтому
исходные файлы вашего менеджера dotfiles не перезаписываются. Не удаляйте
резервную копию до проверки нового окружения.

Разместите конфигурацию в новых каталогах:

```bash
config_dir=${XDG_CONFIG_HOME:-$HOME/.config}
mkdir -p "$config_dir/hypr" "$config_dir/hyprstack" "$config_dir/systemd/user"
cp -R shell/assets/hyprland/config/. "$config_dir/hypr/"
cp -R distribution/defaults/hyprstack/. "$config_dir/hyprstack/"
export PATH="$HOME/.local/bin:$PATH"
hyprstack scheme set -n hyprstack-catppuccin -m dark
```

Только на Arch-based системах скопируйте пользовательскую службу. На NixOS
она уже предоставляется системным модулем; этот шаг пропустите.

```bash
cp distribution/systemd/user/hyprstack-session.service "$config_dir/systemd/user/"
```

Если работает пользовательский systemd, перечитайте службу:

```bash
if command -v systemctl >/dev/null 2>&1 && systemctl --user show-environment >/dev/null 2>&1; then
    systemctl --user daemon-reload
fi
```

Добавьте `$HOME/.local/bin` в `PATH` своего профиля входа, если этого ещё нет.
При собственных переменных XDG они должны быть одинаковыми в TTY и графическом
сеансе. В системе с systemd убедитесь, что `dbus-update-activation-environment`
доступен: в Arch-based системах его предоставляет пакет `dbus`,
на NixOS — соответствующая конфигурация D-Bus. `systemctl --user enable` для службы Hyprstack не требуется:
она запускается конфигурацией Hyprland. Без пользовательского systemd
используется встроенный менеджер сеанса.

## 6. Войдите в Hyprland и проверьте запуск

Выберите Hyprland в менеджере входа либо запустите его из TTY способом,
предусмотренным вашей установкой. Для Hyprland с системным запускателем:

```bash
start-hyprland
```

Подробности: [первый запуск Hyprland](https://wiki.hypr.land/0.56.0/Getting-Started/Master-Tutorial/).
После входа откройте терминал и выполните:

```bash
hyprstack-doctor
hyprctl configerrors
```

Проверки должны пройти, а список ошибок конфигурации — быть пустым.
Отключите автозапуск прежней панели или демона уведомлений, если они запускаются
из других пользовательских служб.

```bash
hyprstack-session restart
```

Эта команда перезапускает оболочку. Для остановки используйте
`hyprstack-session stop`, для запуска — `hyprstack-session start`.

## 7. Настройте окружение под себя

- Выберите приложения в настройках оболочки и `hyprstack/hypr-vars.lua`.
- Укажите свою раскладку клавиатуры в `hyprstack/local.lua`; по умолчанию — `us`.
- При необходимости задайте собственные экраны в `hyprstack/monitors.lua`.
  Файл поставляется пустым; режим, расположение и масштаб по умолчанию выбирает
  Hyprland автоматически. Профили конкретного железа не устанавливаются.
- Выберите обои в настройках. До этого используется однотонный фон темы.
- Включите погоду только при необходимости и выберите город.

Подробнее: [настройки](CONFIGURATION.md), [диагностика, обновление и восстановление](MAINTENANCE.md).
