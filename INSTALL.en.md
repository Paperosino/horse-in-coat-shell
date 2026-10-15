[Русский](INSTALL.md) · [Home](README.en.md)

# Installation

Follow the steps in order as your regular user. Use `sudo` only for system
packages. The commands assume Bash. Resolve any command failure before
continuing to the next step.

## 1. Check compatibility

| Component | Requirement |
| --- | --- |
| Hyprland | **0.56.2**, with Lua configuration |
| Hyprland headers | The same build and ABI as the installed compositor |
| Quickshell | **≥ 0.3.1**, including Hyprland, PAM, Polkit, PipeWire, Bluetooth, UPower, notifications and tray modules |
| Qt | **≥ 6.9**, a compatible build shared by Quickshell and Hyprstack |
| Compiler | C++23, for example GCC ≥ 14 |
| Tools | CMake ≥ 3.22, Ninja, pkg-config, gettext, Python ≥ 3.10, Pillow |

Installed and running Hyprland builds must match. Log out after updating the
compositor. Rebuild the native extension after an ABI change. A Hyprland version
other than 0.56.2 requires a compatible Hyprstack release.

Build and graphical checks have been run on CachyOS. The other sections describe
dependency preparation; they do not claim a verified installation on every OS
release. Avoid mixing packages from different distribution releases.

## 2. Install distribution dependencies

The build needs Qt Core, Gui, Qml, Quick, QuickControls2, Concurrent, Sql,
Network, DBus and ShaderTools, Qt Quick private headers, libqalculate,
libsensors, Hyprland headers, pixman, libdrm, libinput, libudev, Wayland,
xkbcommon and Pango/Cairo. M3Shapes, fonts and Material Symbols are bundled.

Check repository versions first. **The Hyprland installation commands below
apply only when version 0.56.2 is available.** Otherwise, prepare a compatible
stack using the [Hyprland documentation](https://wiki.hypr.land/Getting-Started/Installation/)
and [Quickshell documentation](https://quickshell.org/docs/v0.3.0/guide/install-setup/),
then continue with step 3. Hyprstack does not add third-party repositories.

<a id="arch"></a>

### Arch Linux / CachyOS / EndeavourOS / Manjaro

1. Check available versions:

   ```bash
   pacman -Si hyprland quickshell qt6-base
   ```

   Manjaro branches may lag behind Arch; the same version requirements apply.

2. With compatible versions available, perform a full system upgrade and install
   the stack and build dependencies:

   ```bash
   sudo pacman -Syu --needed base-devel git cmake ninja pkgconf gettext \
     hyprland quickshell qt6-base qt6-declarative qt6-shadertools \
     qt6-svg qt6-imageformats qt6-wayland libqalculate lm_sensors \
     pixman libdrm libinput systemd-libs wayland libxkbcommon pango cairo \
     python python-pillow
   ```

3. Install shell utilities:

   ```bash
   sudo pacman -S --needed kitty firefox fuzzel btop pavucontrol \
     wl-clipboard cliphist grim slurp wf-recorder swappy libnotify \
     brightnessctl networkmanager pipewire pipewire-pulse wireplumber \
     polkit hyprlock hyprpicker xdg-utils xdg-user-dirs libxml2 adwaita-icon-theme
   ```

4. Continue with step 3 below.

<a id="fedora"></a>

### Fedora

1. Inspect package versions, including matching `hyprland-devel`:

   ```bash
   dnf info hyprland hyprland-devel quickshell qt6-qtbase
   ```

   Quickshell availability depends on your release and repositories. If absent
   or older than 0.3.1, use the options in its
   [official installation guide](https://quickshell.org/docs/v0.3.0/guide/install-setup/).

2. Install a compatible stack and build dependencies:

   ```bash
   sudo dnf install git cmake ninja-build gcc-c++ pkgconf-pkg-config gettext \
     hyprland hyprland-devel quickshell \
     qt6-qtbase-devel qt6-qtbase-private-devel qt6-qtdeclarative-devel \
     qt6-qtshadertools-devel qt6-qtsvg qt6-qtimageformats qt6-qtwayland \
     libqalculate-devel lm_sensors-devel python3-pillow \
     pixman-devel libdrm-devel libinput-devel systemd-devel wayland-devel \
     libxkbcommon-devel pango-devel cairo-devel
   ```

3. Install shell utilities:

   ```bash
   sudo dnf install kitty firefox fuzzel btop pavucontrol qalculate \
     wl-clipboard cliphist grim slurp wf-recorder swappy libnotify \
     brightnessctl NetworkManager pipewire pipewire-pulseaudio wireplumber \
     polkit hyprlock hyprpicker xdg-utils xdg-user-dirs libxml2 adwaita-icon-theme
   ```

4. Continue with step 3 below. Check package contents in the
   [Fedora catalogue](https://packages.fedoraproject.org/pkgs/qt6-qtdeclarative/qt6-qtdeclarative-devel/).

<a id="debian-ubuntu"></a>

### Debian / Ubuntu

1. Refresh package information and inspect versions:

   ```bash
   sudo apt update
   apt-cache policy hyprland hyprland-dev quickshell qt6-base-dev
   ```

   Ubuntu 24.04 and Debian 13 ship an older Qt than required. Ubuntu 26.04 has
   a sufficiently recent Qt, but its stock Hyprland 0.53.3 does not meet the
   0.56.2 requirement. Testing/Unstable and newer releases still need version
   checks. This section assumes compatible Hyprland, headers and Quickshell
   are available from your chosen source. Quickshell lists Debian and Ubuntu
   installation options in its [official guide](https://quickshell.org/docs/v0.3.0/guide/install-setup/).

2. Install build dependencies:

   ```bash
   sudo apt install build-essential git cmake ninja-build pkg-config gettext \
     qt6-base-dev qt6-base-private-dev qt6-declarative-dev qt6-declarative-private-dev \
     qt6-shadertools-dev libqt6svg6 qt6-image-formats-plugins qt6-wayland \
     libqt6sql6-sqlite libqalculate-dev libsensors-dev python3 python3-pil \
     libpixman-1-dev libdrm-dev libinput-dev libudev-dev libwayland-dev \
     libxkbcommon-dev libpango1.0-dev libcairo2-dev
   ```

   If necessary, install GCC ≥ 14 from your release's repositories and select
   it with `CXX` before configuring CMake.

3. Only with compatible packages available, install the stack:

   ```bash
   sudo apt install hyprland hyprland-dev quickshell
   ```

4. Install QML modules, which are separate from development packages:

   ```bash
   sudo apt install qml6-module-qtqml qml6-module-qtqml-models \
     qml6-module-qtqml-workerscript qml6-module-qtquick \
     qml6-module-qtquick-controls qml6-module-qtquick-layouts \
     qml6-module-qtquick-effects qml6-module-qtquick-shapes \
     qml6-module-qtquick-templates qml6-module-qtquick-window
   ```

5. Install shell utilities:

   ```bash
   sudo apt install kitty firefox fuzzel btop pavucontrol qalc \
     wl-clipboard cliphist grim slurp wf-recorder swappy libnotify-bin \
     brightnessctl network-manager pipewire pipewire-pulse wireplumber \
     polkitd hyprlock hyprpicker xdg-utils xdg-user-dirs libxml2-utils adwaita-icon-theme
   ```

6. Continue with step 3 below. Stock Ubuntu package versions:
   [Hyprland](https://packages.ubuntu.com/search?keywords=hyprland),
   [Qt](https://packages.ubuntu.com/search?keywords=qt6-base-dev).
   Stock Debian Qt: [Debian 13 package](https://packages.debian.org/trixie/qt6-base-dev).

<a id="opensuse"></a>

### openSUSE Tumbleweed / Slowroll

1. Check package availability and versions:

   ```bash
   zypper info hyprland hyprland-devel quickshell qt6-base-devel
   ```

   Leap has the same requirements; a compatible stack is not assumed to be
   available. If Quickshell is missing, use a source or build method listed
   in its [official guide](https://quickshell.org/docs/v0.3.0/guide/install-setup/).

2. Install a compatible stack and build dependencies:

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

3. Install shell utilities:

   ```bash
   sudo zypper install kitty firefox fuzzel btop pavucontrol qalculate \
     wl-clipboard cliphist grim slurp wf-recorder swappy libnotify-tools \
     brightnessctl NetworkManager pipewire pipewire-pulseaudio wireplumber \
     polkit hyprlock hyprpicker xdg-utils xdg-user-dirs libxml2-tools adwaita-icon-theme
   ```

4. Continue with step 3 below. For package names in your branch, use
   `zypper search` or the [openSUSE catalogue](https://software.opensuse.org/).

### Optional components and system services

Networking uses a running NetworkManager; audio uses PipeWire and WirePlumber.
Keep the service setup used by your distribution. A user D-Bus session is also
required. Quickshell provides the built-in Polkit agent; do not run another
Polkit agent or notification daemon alongside it.

Install BlueZ for Bluetooth, UPower for battery information,
power-profiles-daemon for power profiles, ddcutil for external monitor brightness,
and wtype for typing a selected emoji, if needed. Use package names from your
distribution. A machine without Bluetooth, a battery or an external monitor
does not need substitute devices.

The file manager is opened through `xdg-open`; install one of your choice.
Firefox and kitty are configurable defaults. `grim`/`slurp`/`swappy` provide
screenshot tools, `wf-recorder` provides recording and `hyprpicker` provides
colour picking. If an optional package is missing from your branch, install it
separately to enable the associated feature.

## 3. Verify the stack

```bash
Hyprland --version-json
qs --version
pkg-config --modversion Qt6Core hyprland
c++ --version
cmake --version
test -r /etc/pam.d/hyprlock
```

Hyprland must report version 0.56.2 and a nonempty `abiHash`; Quickshell must be
at least 0.3.1 and Qt at least 6.9. The last command checks the system PAM lock
service. Install `hyprlock` if it fails; do not copy someone else's PAM files
into `/etc/pam.d`.

CMake also compares header and compositor ABIs and stops if they differ.
If Quickshell lacks PAM or Polkit, rebuild it with those modules using the
Quickshell documentation.

## 4. Get the source and build

Clone the repository:

```bash
git clone https://github.com/hase9awa/hyprstack-shell.git
cd hyprstack-shell
```

Alternatively, use **Code → Download ZIP**, extract the archive and open
a terminal in the directory containing `CMakeLists.txt`. No Git submodules are required.

```bash
cmake -S . -B build -G Ninja \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_INSTALL_PREFIX="$HOME/.local" \
  -DCMAKE_INSTALL_DATADIR="${XDG_DATA_HOME:-$HOME/.local/share}"
cmake --build build --parallel 2
cmake --install build
```

Use `--parallel 1` on systems with limited memory. Do not run these commands
with `sudo`. The audio visualiser is excluded from the default build; its
additional dependencies are described in [CONFIGURATION.md](CONFIGURATION.md).

## 5. Back up and place configuration files

**Log out of the graphical session and use a TTY for this step.** The new Lua
configuration replaces your Hyprland configuration. All parts must be in place
before starting the compositor again.

Return to the downloaded source directory. Move existing configuration into
a unique backup:

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

printf 'Backup: %s\n' "$backup_dir"
```

Save the printed path. Symlinks are moved as symlinks, so source files managed
by your dotfiles tool are not overwritten. Keep the backup until the new desktop
has been checked.

Copy configuration into the new directories:

```bash
config_dir=${XDG_CONFIG_HOME:-$HOME/.config}
mkdir -p "$config_dir/hypr" "$config_dir/hyprstack" "$config_dir/systemd/user"
cp -R shell/assets/hyprland/config/. "$config_dir/hypr/"
cp -R distribution/defaults/hyprstack/. "$config_dir/hyprstack/"
cp distribution/systemd/user/hyprstack-session.service "$config_dir/systemd/user/"
export PATH="$HOME/.local/bin:$PATH"
hyprstack scheme set -n hyprstack-catppuccin -m dark
```

If user systemd is available, reload its configuration:

```bash
if command -v systemctl >/dev/null 2>&1 && systemctl --user show-environment >/dev/null 2>&1; then
    systemctl --user daemon-reload
fi
```

Add `$HOME/.local/bin` to your login profile's `PATH` if necessary. Custom XDG
variables must match between the TTY and graphical session. On systemd systems,
ensure `dbus-update-activation-environment` is available: Debian/Ubuntu provides
it in `dbus-bin`; other distributions include it in their D-Bus packages.
Do not enable the Hyprstack user service: Hyprland starts it through its
configuration. Without user systemd, the built-in session manager is used.

## 6. Log into Hyprland and check startup

Select Hyprland in your display manager, or start it from a TTY using your
installation's method. For Hyprland installations with its session launcher:

```bash
start-hyprland
```

See the [Hyprland first-launch guide](https://wiki.hypr.land/0.56.0/Getting-Started/Master-Tutorial/).
After logging in, open a terminal and run:

```bash
~/.local/bin/hyprstack-doctor
hyprctl configerrors
```

Checks should pass and configuration errors should be empty. Disable your
previous panel or notification daemon if started by other user services.

```bash
hyprstack-session restart
```

Use `hyprstack-session stop` to stop the shell and `hyprstack-session start`
to start it.

## 7. Choose your settings

- Set applications in the shell settings and `hyprstack/hypr-vars.lua`.
- Set your keyboard layout in `hyprstack/local.lua`; the default is `us`.
- Add output overrides to `hyprstack/monitors.lua` if needed. It ships empty;
  Hyprland selects mode, position and scale automatically. No machine-specific
  hardware profiles are installed.
- Choose a wallpaper in settings. Until then, a solid theme background is used.
- Enable weather and select a city only if desired.

See [configuration (Russian)](CONFIGURATION.md) and
[diagnostics, updates and recovery (Russian)](MAINTENANCE.md).
