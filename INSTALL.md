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

### 1. Установка одной командой (рекомендуется)

Понадобятся `git`, `sudo` и `pacman`. Запускайте обычным пользователем:

```bash
git clone https://github.com/Paperosino/horse-in-coat-shell.git hics
cd hics
./install.sh
```

Установщик сам определяет и устанавливает **все обязательные зависимости
запуска и сборки из `packaging/arch/PKGBUILD`**, проверяет Hyprland **0.56.2**
и ABI заголовков, собирает пакет и устанавливает его через `pacman -U`.
`sudo` и pacman запрашивают пароль/подтверждение в терминале. При ошибке
установка завершается с ненулевым кодом, а готовый пакет остаётся в исходниках.
Отдельно копировать список библиотек в терминал больше не требуется.

Готовый пакет можно установить без компилятора и зависимостей сборки:

```bash
./install.sh --package ~/Загрузки/hic-shell-1.1.1-67-x86_64.pkg.tar.zst
```

Pacman сам установит его обязательные зависимости из настроенных репозиториев.
Для просмотра плана без изменений:

```bash
./install.sh --dry-run
./install.sh --package /путь/к/hic-shell.pkg.tar.zst --dry-run
```

Пакет содержит собственный Quickshell **v0.3.2** и приватный Qt runtime в
`/usr/share/hics/qs`. Системный `quickshell` для пакетного варианта не нужен.
Обновление выполняется тем же сценарием; исходники и пакет собираются без root.

Автоматически включаются системные `hics-system.service`, `hics-memory.service`
и пользовательские `hic-session.service`, `hics-desktop.service`,
`hics-displays.service`, `hics-configuration.service`. В работающем сеансе
Hyprland неактивные службы запускаются сразу. Работающие пользовательские службы
сохраняются без перезапуска, включая владельца блокировки и операции отката.
Их обновление применяется после выхода и нового входа; при установке из TTY/chroot —
при следующем подходящем входе. Экранный диктор включается настройкой доступности,
а не автоматически для всех. Службы сторонних пакетов не перенастраиваются
вместо уже выбранных пользователем сетевых и других системных служб.

Во время пакетного обновления автоматическое наблюдение Hyprland за конфигами
временно приостанавливается, затем возвращается; исходное отключение пользователем
сохраняется. Не запускайте явную перезагрузку конфигурации во время распаковки
пакета. При невозможности включить защиту установщик выводит предупреждение.

При обновлении Hyprland и открытые приложения сохраняются. После изменения
нативных плагинов потребуется новый графический сеанс; установщик не выгружает
плагины на ходу. `pacman -Sy`, принудительный downgrade и полное обновление ОС
без запроса не выполняются. Если репозитории устарели, обновите систему обычным
для своего дистрибутива способом и повторите установку.

Файловые менеджеры, архиваторы, VPN-плагины, Timeshift и другие `optdepends`
остаются на выбор пользователя: устанавливать одновременно все альтернативные
и потенциально конфликтующие программы не требуется.

Только сборка пакета: `packaging/arch/build-package.sh`.
Сборка и установка: `packaging/arch/build-package.sh --install` (эквивалент
`./install.sh`). Личная конфигурация не перезаписывается; первичная настройка
нового Hyprland описана в разделе 3 ниже.

### 2. Ручная установка (необязательно)

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

После пакетной установки выберите **HICS** в менеджере входа. При первом
запуске сеанс создаёт только отсутствующие настройки в `$XDG_CONFIG_HOME/hics`
(по умолчанию `~/.config/hics`). Чужая конфигурация Hyprland не заменяется.
У существующей распознанной конфигурации HICS сохраняются локальные настройки,
включая режимы мониторов. Без менеджера входа выполните `hics-start` из TTY.
Для проверки подготовки без запуска композитора: `hics-start --prepare`.

Следующая процедура — **необязательный ручной перенос**, если вы осознанно
хотите заменить прежнюю конфигурацию. Для обычной пакетной установки она не нужна.

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

Войдите в **HICS** через менеджер входа или выполните `hics-start` из TTY.
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
