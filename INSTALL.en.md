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

Supported families are **Arch Linux and Arch-based distributions**, plus
**NixOS**. Desktop build and graphical checks have been run on CachyOS; NixOS
uses a separate package and configuration modules. Fedora, Debian/Ubuntu and
openSUSE are outside the supported platforms. Do not mix packages from different
distribution releases.

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
     hyprland quickshell nlohmann-json qt6-base qt6-declarative qt6-shadertools \
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

<a id="nixos"></a>

### NixOS

Use this repository's Nix package. Hyprland, Quickshell and Qt come from one
pinned nixpkgs; the native plugin uses the same Hyprland development headers.
The Nix build retains the compositor ABI check.

1. Add an input to your existing NixOS configuration's `flake.nix`:

   ```nix
   inputs.hyprstack.url = "github:hase9awa/hyprstack-shell";
   ```

2. Include `hyprstack` in `outputs` and add the module to your system's `modules`:

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

   Keep your other inputs, modules and system settings. The module enables a
   matching Hyprland, hyprlock PAM and the shell's user service. It does not set
   monitors, GPU drivers, disks or hardware preferences. Do not override
   `programs.hyprland.package` with another package: the module rejects mismatches.

3. Apply your configuration and start a new session:

   ```bash
   sudo nixos-rebuild switch --flake .#YOUR_HOST
   ```

   The shell uses NetworkManager for networking and PipeWire/WirePlumber for
   audio. Enable the services you need in your NixOS configuration. The module
   preserves your choice of networking and audio setup.

4. Install user configuration using one of these approaches:

   - **Home Manager:** import `hyprstack.homeManagerModules.default` in the user
     module and enable `programs.hyprstack.enable`. Back up an existing
     `~/.config/hypr` and `~/.config/hyprstack/hypr-user.lua` first: Home Manager
     does not silently overwrite conflicting files. Missing preferences are
     initialized as writable files and remain editable from the shell.

     ```nix
     home-manager.users.YOUR_USER = {
       imports = [ hyprstack.homeManagerModules.default ];
       programs.hyprstack.enable = true;
     };
     ```

   - **Without Home Manager:** clone the source and follow the backup and
     configuration placement commands in step 5 below. Skip CMake and the
     `~/.local` program installation; the NixOS module already installs the programs.

     ```bash
     git clone https://github.com/hase9awa/hyprstack-shell.git
     cd hyprstack-shell
     ```

5. Log into Hyprland and run `hyprstack-doctor` and `hyprctl configerrors`.
   Update the `hyprstack` input in your Nix configuration, rebuild your system
   and start a new session for upgrades. Do not copy files over Home Manager's
   managed configuration.

Steps 3–4 below describe the Arch-based source build. On NixOS, use the package
and modules above.

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
export PATH="$HOME/.local/bin:$PATH"
hyprstack scheme set -n hyprstack-catppuccin -m dark
```

On Arch-based systems, copy the user service below. On NixOS, the system
module already provides it; skip this command.

```bash
cp distribution/systemd/user/hyprstack-session.service "$config_dir/systemd/user/"
```

If user systemd is available, reload its configuration:

```bash
if command -v systemctl >/dev/null 2>&1 && systemctl --user show-environment >/dev/null 2>&1; then
    systemctl --user daemon-reload
fi
```

Add `$HOME/.local/bin` to your login profile's `PATH` if necessary. Custom XDG
variables must match between the TTY and graphical session. On systemd systems,
ensure `dbus-update-activation-environment` is available: Arch-based systems
provide it in `dbus`; NixOS provides it through its D-Bus configuration.
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
hyprstack-doctor
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
