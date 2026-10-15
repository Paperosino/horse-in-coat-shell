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

На CachyOS проверены сборка и работа интерфейса. Остальные разделы описывают
подготовку зависимостей, а не подтверждённую поддержку каждого выпуска ОС.
Не смешивайте пакеты разных выпусков дистрибутива ради одного компонента.

## 2. Установите зависимости своего дистрибутива

Для сборки нужны Qt Core, Gui, Qml, Quick, QuickControls2, Concurrent, Sql,
Network, DBus и ShaderTools, приватные заголовки Qt Quick, libqalculate, libsensors,
заголовки Hyprland, pixman, libdrm, libinput, libudev, Wayland, xkbcommon и
Pango/Cairo. M3Shapes, шрифты и Material Symbols уже включены в исходники.

Сначала проверьте версии пакетов в своей ветке. **Команды установки Hyprland
ниже применимы только при наличии версии 0.56.2.** Если её нет, подготовьте
совместимый стек по [документации Hyprland](https://wiki.hypr.land/Getting-Started/Installation/)
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
     hyprland quickshell qt6-base qt6-declarative qt6-shadertools \
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

<a id="fedora"></a>

### Fedora

1. Проверьте пакеты, включая совпадение версии `hyprland-devel`:

   ```bash
   dnf info hyprland hyprland-devel quickshell qt6-qtbase
   ```

   Наличие подходящего Quickshell зависит от выпуска и подключённых
   репозиториев. Если он отсутствует или старее 0.3.1, используйте варианты
   установки из [официальной инструкции](https://quickshell.org/docs/v0.3.0/guide/install-setup/).

2. Установите совместимый стек и инструменты:

   ```bash
   sudo dnf install git cmake ninja-build gcc-c++ pkgconf-pkg-config gettext \
     hyprland hyprland-devel quickshell \
     qt6-qtbase-devel qt6-qtbase-private-devel qt6-qtdeclarative-devel \
     qt6-qtshadertools-devel qt6-qtsvg qt6-qtimageformats qt6-qtwayland \
     libqalculate-devel lm_sensors-devel python3-pillow \
     pixman-devel libdrm-devel libinput-devel systemd-devel wayland-devel \
     libxkbcommon-devel pango-devel cairo-devel
   ```

3. Установите программы оболочки:

   ```bash
   sudo dnf install kitty firefox fuzzel btop pavucontrol qalculate \
     wl-clipboard cliphist grim slurp wf-recorder swappy libnotify \
     brightnessctl NetworkManager pipewire pipewire-pulseaudio wireplumber \
     polkit hyprlock hyprpicker xdg-utils xdg-user-dirs libxml2 adwaita-icon-theme
   ```

4. Перейдите к шагу 3 ниже. Имена и состав пакетов можно проверить в
   [каталоге Fedora](https://packages.fedoraproject.org/pkgs/qt6-qtdeclarative/qt6-qtdeclarative-devel/).

<a id="debian-ubuntu"></a>

### Debian / Ubuntu

1. Обновите сведения о пакетах и проверьте версии:

   ```bash
   sudo apt update
   apt-cache policy hyprland hyprland-dev quickshell qt6-base-dev
   ```

   Ubuntu 24.04 и Debian 13 не подходят со штатным Qt. В Ubuntu 26.04 Qt
   достаточно новый, но штатный Hyprland 0.53.3 не соответствует требованию
   0.56.2. Testing/Unstable и более новые выпуски также требуют проверки версий.
   Этот раздел предполагает, что совместимые Hyprland с заголовками и
   Quickshell уже доступны из выбранного вами источника. Способ установки
   Quickshell для Debian/Ubuntu описан у [авторов проекта](https://quickshell.org/docs/v0.3.0/guide/install-setup/).

2. Установите инструменты и заголовки:

   ```bash
   sudo apt install build-essential git cmake ninja-build pkg-config gettext \
     qt6-base-dev qt6-base-private-dev qt6-declarative-dev qt6-declarative-private-dev \
     qt6-shadertools-dev libqt6svg6 qt6-image-formats-plugins qt6-wayland \
     libqt6sql6-sqlite libqalculate-dev libsensors-dev python3 python3-pil \
     libpixman-1-dev libdrm-dev libinput-dev libudev-dev libwayland-dev \
     libxkbcommon-dev libpango1.0-dev libcairo2-dev
   ```

   При необходимости установите GCC ≥ 14 из репозиториев своего выпуска
   и выберите его через `CXX` перед запуском CMake.

3. При наличии именно совместимых пакетов установите стек:

   ```bash
   sudo apt install hyprland hyprland-dev quickshell
   ```

4. Установите модули QML: в Debian/Ubuntu они отделены от пакетов разработки.

   ```bash
   sudo apt install qml6-module-qtqml qml6-module-qtqml-models \
     qml6-module-qtqml-workerscript qml6-module-qtquick \
     qml6-module-qtquick-controls qml6-module-qtquick-layouts \
     qml6-module-qtquick-effects qml6-module-qtquick-shapes \
     qml6-module-qtquick-templates qml6-module-qtquick-window
   ```

5. Установите программы оболочки:

   ```bash
   sudo apt install kitty firefox fuzzel btop pavucontrol qalc \
     wl-clipboard cliphist grim slurp wf-recorder swappy libnotify-bin \
     brightnessctl network-manager pipewire pipewire-pulse wireplumber \
     polkitd hyprlock hyprpicker xdg-utils xdg-user-dirs libxml2-utils adwaita-icon-theme
   ```

6. Перейдите к шагу 3 ниже. Сведения о штатных версиях Ubuntu:
   [Hyprland](https://packages.ubuntu.com/search?keywords=hyprland),
   [Qt](https://packages.ubuntu.com/search?keywords=qt6-base-dev).
   Штатный Qt Debian: [пакет Debian 13](https://packages.debian.org/trixie/qt6-base-dev).

<a id="opensuse"></a>

### openSUSE Tumbleweed / Slowroll

1. Проверьте версии и доступность пакетов:

   ```bash
   zypper info hyprland hyprland-devel quickshell qt6-base-devel
   ```

   Для Leap требования те же; наличие совместимого стека не предполагается.
   Если Quickshell отсутствует, выберите источник или сборку по
   [официальной инструкции](https://quickshell.org/docs/v0.3.0/guide/install-setup/).

2. Установите совместимый стек и зависимости:

   ```bash
   sudo zypper install git cmake ninja gcc-c++ pkgconf-pkg-config gettext-tools \
     hyprland hyprland-devel quickshell \
     qt6-base-devel qt6-declarative-devel qt6-shadertools-devel \
     qt6-core-private-devel qt6-gui-private-devel qt6-qml-private-devel qt6-quick-private-devel \
     libQt6Svg6 qt6-imageformats qt6-wayland-integration qt6-sql-sqlite \
     libqalculate-devel libsensors4-devel python3-Pillow \
     pixman-devel libdrm-devel libinput-devel libudev-devel wayland-devel \
     libxkbcommon-devel pango-devel cairo-devel
   ```

3. Установите программы оболочки:

   ```bash
   sudo zypper install kitty firefox fuzzel btop pavucontrol qalculate \
     wl-clipboard cliphist grim slurp wf-recorder swappy libnotify-tools \
     brightnessctl NetworkManager pipewire pipewire-pulseaudio wireplumber \
     polkit hyprlock hyprpicker xdg-utils xdg-user-dirs libxml2-tools adwaita-icon-theme
   ```

4. Перейдите к шагу 3 ниже. Если имя пакета отличается в вашей ветке,
   уточните его через `zypper search` или [каталог openSUSE](https://software.opensuse.org/).

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
cp distribution/systemd/user/hyprstack-session.service "$config_dir/systemd/user/"
export PATH="$HOME/.local/bin:$PATH"
hyprstack scheme set -n hyprstack-catppuccin -m dark
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
доступен: на Debian/Ubuntu его предоставляет `dbus-bin`, в других системах —
пакеты D-Bus. `systemctl --user enable` для службы Hyprstack не требуется:
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
~/.local/bin/hyprstack-doctor
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
