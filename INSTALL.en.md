[Русский](INSTALL.md) · [Home](README.en.md)

# Installation

[Arch Linux and derivatives](#arch) · [NixOS](#nixos)

Requires **Hyprland 0.56.2**; headers must match the installed compositor's
ABI. Build requirements: C++23, CMake ≥ 3.27, Python ≥ 3.11.

**Option A (package, recommended)** does not depend on the system Quickshell
and Qt packages — the package bundles its own runtime.
**Option B (manual build)** requires the system **Quickshell ≥ 0.3.1** with
Hyprland, PAM and Polkit modules, and **Qt ≥ 6.9**.

<a id="arch"></a>

## One-command Arch installation

Run as a regular user: `./install.sh`. It installs missing runtime and build
dependencies from `packaging/arch/PKGBUILD`, validates Hyprland 0.56.2 and its
headers, builds a package, and installs it through pacman. Sudo prompts normally.
`./install.sh --package /path/to/hic-shell.pkg.tar.zst` installs a prebuilt package
and its runtime dependencies without build tools. Add `--dry-run` to inspect the plan.

The package enables `hics-system` and `hics-memory` system services, and
`hic-session`, `hics-desktop`, `hics-displays`, `hics-configuration` user services.
Active Hyprland sessions start all four user services immediately. Offline/chroot
installation enables units for the next suitable session. Screen reader and
optional packages remain user-controlled. Existing configuration is preserved;
initial compositor configuration is described below. No partial database refresh
or automatic full OS upgrade is performed. Native plugin updates need a new
compositor session; user applications are preserved during shell restarts.

## Arch Linux / CachyOS / EndeavourOS / Manjaro

### 1. Dependencies

Check the Hyprland version in the repositories. Continue only if Hyprland
**0.56.2** is available:

```bash
pacman -Si hyprland
```

Common dependencies and applications:

```bash
sudo pacman -Syu --needed base-devel git cmake ninja pkgconf gettext \
  hyprland libqalculate lm_sensors libcups python python-pillow kitty firefox \
  fuzzel btop pavucontrol wl-clipboard cliphist grim slurp wf-recorder \
  swappy libnotify brightnessctl networkmanager libnm libsecret pipewire pipewire-pulse \
  wireplumber polkit hyprlock hyprpicker xdg-utils xdg-user-dirs \
  libxml2 adwaita-icon-theme dbus udisks2 qt5ct qt6ct libxcursor xorg-xrdb
```

### 2. Installation

#### Option A: package (recommended)

Run without `sudo`:

```bash
git clone https://github.com/Paperosino/horse-in-coat-shell.git hics
cd hics
packaging/arch/build-package.sh --install
```

The script installs any missing runtime and build dependencies and builds the
`hic-shell` package with a bundled runtime: its own Quickshell
**v0.3.2** and private Qt libraries in `/usr/share/hics/qs`. System
updates of the `quickshell` and `qt6-*` packages no longer affect the shell;
the system `quickshell` package is not needed (if the bundle is missing,
the wrapper falls back to the system `qs`). The session service is
installed straight into `/usr/lib/systemd/user`. Update the package by
running the same script: it rebuilds the bundled runtime against the
current system Qt and re-bundles it.
After installation and upgrades, user services are started only in a live
Hyprland session. Already running services are preserved, including the session
lock owner and pending rollback operations. Log out and back in to apply their
update. Inactive user sessions do not start a shell.

During a package upgrade, a temporary user service suspends automatic Hyprland
configuration watching until the pacman transaction finishes. A previously
disabled watcher stays disabled. Do not explicitly reload the configuration
while package files are being replaced. A guard startup failure is reported.

If the shell was previously installed into `$HOME/.local`, remove
`~/.local/share/hics` so the packaged install takes priority
(`HICS_DATA_DIR` still overrides the selection).

#### Option B: manual build into `$HOME/.local`

Additionally install the system Quickshell and Qt:

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

Use `--parallel 1` instead of `--parallel 2` if memory is limited.

<a id="config"></a>

### 3. Configuration

After installing the package, select **HICS** in your display manager. On first
launch it creates only missing settings in `$XDG_CONFIG_HOME/hics` (normally
`~/.config/hics`). An unrelated Hyprland configuration is preserved. Recognized
existing HICS configurations retain local settings, including monitor modes.
Without a display manager, run `hics-start` from a TTY. Use `hics-start --prepare`
to prepare settings without starting the compositor.

The following is an **optional manual migration** for deliberately replacing an
existing configuration. It is unnecessary for a normal package installation.

Log out of the graphical session, open a TTY (**Ctrl+Alt+F3**) and return
to the source directory. Commands assume Bash; XDG paths must match those
in your graphical session.

<a id="backup"></a>

Move the previous configuration to a backup:

```bash
config_dir=${XDG_CONFIG_HOME:-$HOME/.config}
backup_dir=$(mktemp -d "$HOME/hics-backup.XXXXXXXX")
for name in hypr hics systemd/user/hic-session.service; do
    if [ -e "$config_dir/$name" ] || [ -L "$config_dir/$name" ]; then
        mv "$config_dir/$name" "$backup_dir/"
    fi
done
printf 'Backup: %s\n' "$backup_dir"
```

Save the printed path. Then copy the new configuration:

```bash
mkdir -p "$config_dir/hypr" "$config_dir/hics"
cp -R shell/assets/hyprland/config/. "$config_dir/hypr/"
cp -R distribution/defaults/hics/. "$config_dir/hics/"
export PATH="$HOME/.local/bin:$PATH"
hics scheme set -n hics-catppuccin -m dark
```

**Only for option B (manual build):** install the user service.
With the package install (option A) the unit is already installed into
`/usr/lib/systemd/user` — skip this block.
On NixOS, the module provides it; skip this block.

```bash
mkdir -p "$config_dir/systemd/user"
cp distribution/systemd/user/hic-session.service "$config_dir/systemd/user/"
systemctl --user daemon-reload
```

Without user systemd, skip this block; the shell uses its built-in session
manager. Add `~/.local/bin` to your login profile's `PATH`.

### 4. Launch

Select **HICS** in your display manager or run `hics-start` from a TTY.
In a terminal, run:

```bash
hics-doctor
hyprctl configerrors
```

<a id="nixos"></a>

## NixOS

### 1. System module

Add these entries to your existing `flake.nix`, keeping your other inputs
and modules. Replace `YOUR_HOST` with your configuration name:

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

The module installs matching Hyprland, Quickshell, Qt, PAM and the shell service.
Do not override `programs.hyprland.package` with a different package.

### 2. User configuration

If Home Manager is already set up, log out of the graphical session and run
**only the [backup block](#backup)**. Add this to the same `modules` list,
replacing `YOUR_USER` with your username:

```nix
{
  home-manager.users.YOUR_USER = {
    imports = [ hics.homeManagerModules.default ];
    programs.hics.enable = true;
  };
}
```

Both modules must use the same `hics` input. Shell preferences remain
editable through the interface.
Custom Lua: [`programs.hics.extraConfig`](CONFIGURATION.md#экраны-и-клавиатура)
or `~/.config/hics/local.lua`.

**Without Home Manager:** skip this step; copy user configuration after
applying the system configuration, as described below.

### 3. Apply

From your NixOS configuration directory:

```bash
sudo nixos-rebuild switch --flake .#YOUR_HOST
```

<details>
<summary>Copying configuration without Home Manager</summary>

In a TTY, get the files and follow [Arch step 3](#config),
**skipping the user service block**. No CMake build is needed.

```bash
git clone https://github.com/Paperosino/horse-in-coat-shell.git hics
cd hics
```

</details>

Start a new Hyprland session and run `hics-doctor`
and `hyprctl configerrors`.

## Services and optional packages

Networking requires NetworkManager; audio requires PipeWire/WirePlumber.
Enable these services in your system. Disable autostart for your previous
panel, notification daemon and external Polkit agent.

Optional packages: `bluez` for Bluetooth, `upower` for battery information,
`power-profiles-daemon` for power profiles, `ddcutil` for external display
brightness and `wtype` for emoji typing. Install a file manager of your choice.

[Configuration and shortcuts (Russian)](CONFIGURATION.md) ·
[Updates and diagnostics (Russian)](MAINTENANCE.md)

Native system settings use the packaged C++ `hics-system.service`, activated
on the system D-Bus with Polkit authorization. Printing requires CUPS, volumes
use UDisks2, and hardware profiles require power-profiles-daemon. A user-local
installation does not register the privileged service; install the system package
to use these pages.

The package installs the system helper, client, systemd, D-Bus and Polkit files automatically. The user updater also installs the helper through sudo into `/usr/local/bin`; the system service never runs files from the user home.
