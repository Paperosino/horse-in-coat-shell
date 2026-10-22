[English](INSTALL.en.md) · [На главную](README.md)

# Установка hics

[Arch Linux и производные](#arch) · [NixOS](#nixos)

Требуется **Hyprland 0.56.2**; заголовки должны совпадать с установленным
композитором по ABI. Для сборки: C++23, CMake ≥ 3.27, Python ≥ 3.11.

**Вариант А (пакет, рекомендуется)** не зависит от системных пакетов
Quickshell и Qt — пакет вкладывает собственный рантайм.
**Вариант Б (ручная сборка)** требует системный **Quickshell ≥ 0.3.1**
(модули Hyprland, PAM и Polkit) и **Qt ≥ 6.9**.

<a id="arch"></a>

## Arch Linux / CachyOS / EndeavourOS / Manjaro

### 1. Зависимости

Проверьте версию Hyprland в репозиториях. Продолжайте, только если доступен
Hyprland **0.56.2**:

```bash
pacman -Si hyprland
```

Общие зависимости и приложения:

```bash
sudo pacman -Syu --needed base-devel git cmake ninja pkgconf gettext \
  hyprland libqalculate lm_sensors libcups python python-pillow kitty firefox \
  fuzzel btop pavucontrol wl-clipboard cliphist grim slurp wf-recorder \
  swappy libnotify brightnessctl networkmanager libnm libsecret pipewire pipewire-pulse \
  wireplumber polkit hyprlock hyprpicker xdg-utils xdg-user-dirs \
  libxml2 adwaita-icon-theme dbus udisks2 qt5ct qt6ct libxcursor xorg-xrdb
```

### 2. Установка

#### Вариант А: пакет (рекомендуется)

Выполняйте без `sudo`:

```bash
git clone https://github.com/Paperosino/horse-in-coat-shell.git hics
cd hics
packaging/arch/build-package.sh --install
```

Скрипт сам доустановит недостающие зависимости сборки и соберёт пакет
`hic-shell` со вложенным рантаймом: собственный Quickshell **v0.3.2**
и приватные библиотеки Qt в `/usr/share/hics/qs`. Обновления системных
пакетов `quickshell` и `qt6-*` на оболочку не влияют; системный `quickshell`
не нужен (при отсутствии бандла обёртка резервно использует системный `qs`).
Служба сеанса сразу ставится в `/usr/lib/systemd/user`. Обновление пакета
выполняется тем же сценарием: он пересобирает рантайм под текущую системную
Qt и упаковывает его заново.
После установки и обновления пакета активные службы `hic-session.service`
перезапускаются автоматически. Hyprland и открытые приложения продолжают работать;
в неактивных пользовательских сеансах оболочка не запускается.

Если оболочка раньше была установлена в `$HOME/.local`, удалите каталог
`~/.local/share/hics`, чтобы приоритет данных отдал пакетной
установке (`HICS_DATA_DIR` по-прежнему переопределяет выбор).

#### Вариант Б: ручная сборка в `$HOME/.local`

Дополнительно установите системный Quickshell и Qt:

```bash
sudo pacman -S --needed quickshell nlohmann-json qt6-base qt6-declarative \
  qt6-shadertools qt6-svg qt6-imageformats qt6-wayland pixman libdrm \
  libinput systemd-libs wayland libxkbcommon pango cairo
```

```bash
cmake -S . -B build -G Ninja \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_INSTALL_PREFIX="$HOME/.local" \
  -DCMAKE_INSTALL_DATADIR="${XDG_DATA_HOME:-$HOME/.local/share}"
cmake --build build --parallel 2
cmake --install build
sudo python3 distribution/install_system_helper.py "$HOME/.local"
```

При нехватке памяти замените `--parallel 2` на `--parallel 1`.

<a id="config"></a>

### 3. Конфигурация

Завершите графический сеанс, войдите в TTY (**Ctrl+Alt+F3**) и вернитесь
в каталог исходников. Команды рассчитаны на Bash; XDG-пути должны совпадать
с путями графического сеанса.

<a id="backup"></a>

Перенесите прежнюю конфигурацию в резервную копию:

```bash
config_dir=${XDG_CONFIG_HOME:-$HOME/.config}
backup_dir=$(mktemp -d "$HOME/hics-backup.XXXXXXXX")
for name in hypr hics systemd/user/hic-session.service; do
    if [ -e "$config_dir/$name" ] || [ -L "$config_dir/$name" ]; then
        mv "$config_dir/$name" "$backup_dir/"
    fi
done
printf 'Резервная копия: %s\n' "$backup_dir"
```

Сохраните выведенный путь. Затем скопируйте новую конфигурацию:

```bash
mkdir -p "$config_dir/hypr" "$config_dir/hics"
cp -R shell/assets/hyprland/config/. "$config_dir/hypr/"
cp -R distribution/defaults/hics/. "$config_dir/hics/"
export PATH="$HOME/.local/bin:$PATH"
hics scheme set -n hics-catppuccin -m dark
```

**Только для варианта Б (ручная сборка):** установите пользовательскую
службу. При пакетной установке (вариант А) юнит уже установлен в
`/usr/lib/systemd/user` — этот блок пропустите.
На NixOS её предоставляет модуль — этот блок пропустите.

```bash
mkdir -p "$config_dir/systemd/user"
cp distribution/systemd/user/hic-session.service "$config_dir/systemd/user/"
systemctl --user daemon-reload
```

Без пользовательского systemd пропустите этот блок: оболочка использует
встроенный менеджер сеанса. Добавьте `~/.local/bin` в `PATH` своего профиля входа.

### 4. Запуск

Войдите в Hyprland через менеджер входа или `start-hyprland` из TTY.
В терминале выполните:

```bash
hics-doctor
hyprctl configerrors
```

<a id="nixos"></a>

## NixOS

### 1. Системный модуль

Добавьте в существующий `flake.nix`, сохранив остальные входы и модули.
Замените `YOUR_HOST` именем своей конфигурации:

```nix
{
  inputs.hics.url = "github:Paperosino/horse-in-coat-shell";

  outputs = { nixpkgs, hics, ... }: {
    nixosConfigurations.YOUR_HOST = nixpkgs.lib.nixosSystem {
      modules = [
        ./configuration.nix
        hics.nixosModules.default
        { programs.hics.enable = true; }
      ];
    };
  };
}
```

Модуль устанавливает совместимые Hyprland, Quickshell, Qt, PAM и службу оболочки.
Не переопределяйте `programs.hyprland.package` другим пакетом.

### 2. Пользовательская конфигурация

Если Home Manager уже подключён, выйдите из графического сеанса и выполните
**только блок [резервного копирования](#backup)**. Добавьте в тот же список
`modules`, заменив `YOUR_USER` своим пользователем:

```nix
{
  home-manager.users.YOUR_USER = {
    imports = [ hics.homeManagerModules.default ];
    programs.hics.enable = true;
  };
}
```

Оба модуля должны использовать один вход `hics`. Настройки оболочки
останутся доступны для изменения через интерфейс.
Свои Lua-настройки: [`programs.hics.extraConfig`](CONFIGURATION.md#экраны-и-клавиатура)
или `~/.config/hics/local.lua`.

**Без Home Manager:** пропустите этот пункт; после применения системы
скопируйте конфигурацию, как описано ниже.

### 3. Применение

Из каталога конфигурации NixOS:

```bash
sudo nixos-rebuild switch --flake .#YOUR_HOST
```

<details>
<summary>Копирование конфигурации без Home Manager</summary>

Из TTY получите файлы и выполните [пункт 3 для Arch](#config),
**пропустив блок пользовательской службы**. Сборка CMake не нужна.

```bash
git clone https://github.com/Paperosino/horse-in-coat-shell.git hics
cd hics
```

</details>

Войдите в новый сеанс Hyprland и выполните `hics-doctor`
и `hyprctl configerrors`.

## Службы и дополнительные пакеты

Для сети нужен NetworkManager, для звука — PipeWire/WirePlumber; службы должны
быть включены в вашей системе. Отключите автозапуск прежней панели, демона
уведомлений и стороннего агента Polkit.

По необходимости: `bluez` — Bluetooth, `upower` — батарея,
`power-profiles-daemon` — профили питания, `ddcutil` — яркость внешних экранов,
`wtype` — ввод emoji. Файловый менеджер выберите самостоятельно.

[Настройки и клавиши](CONFIGURATION.md) · [Обновление и диагностика](MAINTENANCE.md)

Системные настройки используют C++-службу `hics-system.service`, включённую
в пакет. Она активируется по D-Bus; права подтверждаются через Polkit. Для печати
нужен CUPS, для накопителей — UDisks2, для профилей — power-profiles-daemon.
Пользовательская установка в `~/.local` не регистрирует системную службу:
для этих страниц установите системный пакет оболочки.

Пакет устанавливает демон, клиент, systemd, D-Bus и Polkit автоматически. Пользовательский `./update.sh` также устанавливает системный хелпер через sudo в `/usr/local/bin`; системная служба не запускает файлы из домашнего каталога.
