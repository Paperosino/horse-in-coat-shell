[Русский](README.md)

<p align="center">
  <img src="shell/assets/logo.svg" width="104" alt="horse-in-coat-shell logo">
</p>

<h1 align="center">horse-in-coat-shell</h1>

<p align="center">Four ways to work with windows. One working environment for Hyprland.</p>

<p align="center">
  <a href="INSTALL.en.md">Installation</a> ·
  <a href="MAINTENANCE.md#обновление">Updates</a> ·
  <a href="CONFIGURATION.md">Configuration &amp; keys (Russian)</a> ·
  <a href="#demo">Demo</a>
</p>

horse-in-coat-shell is developed as an independent project with its own direction. Current source and updates: [Paperosino/horse-in-coat-shell](https://github.com/Paperosino/horse-in-coat-shell).

horse-in-coat-shell is a shell for Hyprland with four window modes:
**scrolling** — an infinitely scrollable strip of columns; **stacking** —
floating windows with title bars; **tiling** — classic tiling; **canvas** —
an infinite spatial canvas with zoom, panning and a minimap. Modes switch with
a single key binding and preserve window placement.
Russian is the default language; English and the system language are available
in the settings.

**Tip:** press **Super+F1** to open keyboard shortcuts for the current window mode. You can also switch modes in this window; the shortcut list updates automatically. Super is usually the Windows key.

<a id="demo"></a>

## Showcase

![lavat, Cava and pipes: theme switching and stacking / tiling toggle](docs/media/showcase.gif)

<table>
  <tr>
    <td align="center" width="50%"><img src="docs/media/dashboard.gif" width="100%" alt="Opening the dashboard with calendar, media player and widgets"><br>Dashboard · calendar, media and widgets</td>
    <td align="center" width="50%"><img src="docs/media/panel-tools.gif" width="100%" alt="Close-ups of the notification centre and panel quick actions"><br>Taskbar · notifications and quick actions</td>
  </tr>
  <tr>
    <td align="center"><img src="docs/media/customization.gif" width="100%" alt="Tuning transparency, shadows and UI scale with visible results"><br>Settings · transparency, shadows and scale</td>
    <td align="center"><img src="docs/media/overview.gif" width="100%" alt="Overview of open windows in the light Catppuccin Latte theme"><br>Spatial overview · every window in sight</td>
  </tr>
  <tr>
    <td align="center"><img src="docs/media/trackpad-swipes.gif" width="100%" alt="Scrolling columns and workspaces, navigating the overview with touchpad gestures"><br>Touchpad gestures</td>
  </tr>
</table>

## Features

- **Four window modes.** Scrolling, stacking, tiling and canvas — an infinite
  canvas with zoom, panning, grid snapping and a minimap. One key binding
  cycles the modes; window placement and sizes are remembered.
- **Spatial overview.** Thumbnails of windows and workspaces. In stacking —
  Alt+Tab with window previews.
- **Taskbar.** App grouping, pinning and previews, workspaces, system tray.
  Element composition and placement are configurable.
- **Dock.** A panel with pinned and running apps plus the full app list;
  pin and unpin from the right-click menu.
- **Search & launch.** Applications, calculator, clipboard, theme and
  wallpaper picking.
- **Notifications.** History, grouping, actions and a do-not-disturb mode.
- **System management.** Sound, network, Bluetooth, screenshots and screen
  recording.
- **Dashboard.** Calendar, media player, system state and weather.
- **Appearance.** 18 built-in colour schemes, light and dark modes, accents,
  UI scale, gaps, rounding, transparency and animations.
- **Lock & auth.** A lock screen with PAM and a built-in Polkit agent.

## Settings through the shell

Advanced settings live right in the UI (**Settings**, opened from the panel
or the application launcher) — no configuration files to hand-edit:

- **Display.** Drag-and-drop monitor arrangement (with edge snapping),
  resolution, refresh rate (dependent on the chosen resolution), scale,
  orientation and VRR per output. Changes are saved to `monitors.lua` and
  survive restarts.
- **Keyboard.** Layouts from the full xkb catalogue with a variant per layout,
  a switching shortcut, Caps Lock behaviour, compose key, Num Lock on login,
  key repeat delay and rate. Saved to `keyboard.lua`.
- **Power & lock.** Timeouts for locking, screen off (DPMS) and suspend:
  presets, a custom value in minutes, or never.
- **Dock.** Enable, position (top/bottom) and icon size.
- **Appearance, panels, apps, language & region, keyboard shortcuts** —
  themes, accents, scale, transparency, panel composition, favourite and
  hidden apps, UI language, and a searchable list of active bindings.

## Installation

- [Arch Linux / CachyOS / EndeavourOS / Manjaro](INSTALL.en.md#arch) — the
  recommended way is the package build: `packaging/arch/build-package.sh --install`.
  The package bundles its own Quickshell and a private Qt runtime, so system
  updates of `quickshell` and `qt6-*` never affect the shell.
- [NixOS](INSTALL.en.md#nixos) — package with NixOS/Home Manager modules.

Requires **Hyprland 0.56.2**. After a Hyprland ABI change the native modules
must be rebuilt.

[Updates and recovery](MAINTENANCE.md#обновление).

## First steps

| Binding | Action |
| --- | --- |
| `Super+Ctrl+Shift+M` | Cycle window modes (scrolling → stacking → tiling → canvas) |
| `Super` | Open the dashboard |
| `Super+D` | Application launcher |
| `Super+O` | Overview of windows and workspaces |
| `Super+Return` | Terminal |
| `Super+H` / `Super+L` | Neighbouring window in scrolling |
| `Super+J` / `Super+K` | Neighbouring workspace |
| `Super+Alt+Space` | Toggle floating |
| `Alt+Tab` | Window switcher in stacking |
| `Super+Q` | Close window |
| `Ctrl+Super+L` | Lock the session |

The full, searchable list of bindings is in **Keyboard shortcuts** in the
settings.

In scrolling mode, swipe horizontally with three fingers to scroll columns and
vertically to switch workspaces. Swipe up with four fingers to open overview;
swipe down to activate the selection and close it.
[Gesture settings (Russian)](CONFIGURATION.md#жесты-тачпада).

## Documentation

- [Configuration, shortcuts, themes and weather (Russian)](CONFIGURATION.md)
- [Updates, diagnostics and manual removal (Russian)](MAINTENANCE.md)
- [Third-party components and licences](THIRD_PARTY.md)

## Credits and licence

The project is based on [hyprstack-shell](https://github.com/hase9awa/hyprstack-shell)
and [Caelestia shell](https://github.com/caelestia-dots/shell) — many thanks to
their authors for the thoughtful architecture, code and inspiration.
It also uses [Quickshell](https://quickshell.org/),
[Hyprland](https://hypr.land/), a modified hyprbars,
[Phantomat](https://github.com/kaolti/phantomat) (spatial overview)
and [M3Shapes](https://github.com/soramanew/m3shapes).

Licence: [GPL-3.0](LICENSE). Component and font licences are listed
in [THIRD_PARTY.md](THIRD_PARTY.md).
