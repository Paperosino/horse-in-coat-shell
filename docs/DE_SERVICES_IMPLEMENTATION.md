# Desktop services implementation

User scope (2026-10-25): keyring management + polkit; application permissions,
Flatpak/AppArmor and Pacman removal; file/content search; user backups +
Btrfs/Timeshift integration; presentation quick controls; persistent operations
centre; text input; hung application handling; guided, redacted troubleshooting.
CUPS, GameMode and required backends must ship as package dependencies.

## Architecture and invariants

- Reuse Secret Service/libsecret. Root never receives or decrypts user secrets.
  Polkit gates the hics management entry; it does not replace the keyring password
  or claim to enforce per-client access for the Secret Service protocol.
- Expensive work belongs in a user desktop service, surviving QML reloads.
  Bounded jobs expose real progress, explicit cancellation capability and errors.
- Privileged operations use typed broker operations and separate polkit actions.
  Application removal resolves the owning package from a system desktop file,
  refuses essential desktop/system packages and never bypasses dependency checks.
- Flatpak overrides are per user; native applications are not represented as
  sandboxed without an actual enforcing AppArmor profile. Advanced settings must
  preserve unknown fields and show limits rather than fictitious switches.
- Backups are opt in. Restic handles encryption, Secret Service holds credentials;
  restored files default to a separate destination. System snapshots remain
  distinct from independent backups. Never restore the running system implicitly.
- Search excludes private directories by default and bounds extraction/indexing.
  No shell interpolation. Diagnostics export an allowlist, not raw environment,
  process command lines, network secrets or journal contents by default.
- Presentation mode layers temporary policy over user settings, avoiding stale
  restore snapshots. No private previews/notifications on presentation outputs.
- Never reload native compositor plugins into the working host session. Verify
  graphics in nested compositors; package activation may wait for relogin.

## Delivery checklist

| Area | Delivered behavior | Validation |
| --- | --- | --- |
| Operations centre and automatic panel widget | Persistent native jobs; actual progress/cancellation; automatic appearance; completion linger; errors stay until reviewed; bounded scrolling popup and detailed settings. Aggregates backups, indexing, managed transfers, cleanup, disk maintenance and hics updates | Private-bus restart, producer death/restart, error acknowledgement, automatic widget appearance/expiry and popup lifetime |
| Secret Service management + polkit | Existing GNOME Keyring/libsecret collections, lock/unlock, Seahorse management, PAM diagnostics and password-change recovery instructions; management entry requires polkit | Existing SDDM hooks verified; isolated keyring backup credentials; root never receives vault passwords |
| Application permissions | Per-user Flatpak overrides, basic switches plus advanced flags/folders/USB/bus access; camera portal grants; AppArmor service/profile controls and validated policy editor with backups; preserved autostart entries; Pacman package removal | Invalid identifiers, critical/version protection, exact package-tool arguments, real AppArmor parser in an isolated mount namespace; actual AppInfo UI |
| File/content search | Launcher files/recent results, SQLite FTS and incremental text/PDF extraction, selected/excluded folders, bounded files/bytes/time, opt-in refresh paused on battery/games/high load | Real index/query, private/hidden/symlink exclusion, config changes invalidate index; PDFs deferred by a batch limit remain eligible next run |
| Backup and recovery | Encrypted Restic repository, keyring credentials, hourly schedule, external-disk identity checks, exclusions/compression/bandwidth/free-space controls, snapshot browsing and single-file restore into a separate destination | Real encrypted round trip and integrity check, literal special-character filename, wrong password keeps saved credential, disconnected-disk rejection |
| System snapshots | Existing Snapper/Btrfs Assistant integration and optional Timeshift manager | Manager availability detected; launched outside the restricted worker service so its own polkit authorization works |
| Presentation | Quick toggle, selected output, configurable duration, sleep/DND policy overlay, selected-output private panels/title/previews suppressed, automatic expiry/disconnection cleanup, preferences and QML-reload lease preserved | Graphical activation/restoration, unchanged user's DND/idle settings, selected-output privacy predicate |
| Text input | Searchable emoji/Unicode symbols, favourites and clipboard insertion; Compose settings; Fcitx method/group/layout management; Squeekboard show/hide | Actual C++ ICU lookup, private-bus Fcitx groups/OSK calls, expanded graphical input settings |
| Hung application recovery | Hyprland native ping detection and themed Wait/Force quit dialog; configurable enable/threshold; guarded stable-window identity for termination | Real nested compositor: healthy refusal, SIGSTOP detection, SIGCONT recovery, stale identity refusal, explicit termination of test window |
| Troubleshooting | Guided sound/network/sharing checks, typed repairs with interruption confirmation, advanced service recovery and allowlisted JSON export | Native status/repair adapters, secret-free export and private file permissions; graphical workflow pages |
| Dependencies and activation | Native desktop service, systemd user unit and D-Bus activation in CMake/local installer/Arch hook; CUPS, GameMode, AppArmor, Restic, Seahorse, Fcitx, Squeekboard, Poppler and ICU dependencies | Native build, installer tests and package staging; Timeshift remains optional to preserve distribution Snapper integration |

## Deliberate control boundaries

- hics does not invent a cryptographic vault. GNOME Keyring owns encryption and
  unlock prompts. Polkit authorizes the management UI, not access by every
  Secret Service client. An administrator cannot recover an old encrypted vault
  without its password. Passwordless login cannot supply a missing password.
- Ordinary native applications are not automatically sandboxed. AppArmor requires
  kernel support and a matching loaded/enforcing profile. A portal camera grant
  does not revoke direct camera-device access. PulseAudio socket access may grant
  microphone and playback together; the UI states this.
- Existing running applications may retain grants until restarted. Advanced
  Flatpak settings expose supported CLI flags rather than fictitious universal
  switches. System-wide overrides remain visible in effective permissions.
- Presentation identifies the output and hides hics private surfaces there; the
  actual sharing source must be selected in the application's portal dialog.
  It does not hide private content inside arbitrary application windows.
- The operations centre tracks work started/registered through hics. LocalSend,
  KDE Connect, Blueman and other independent applications own their own progress.
- Timeshift is optional: this machine's cachyos-snapper-support conflicts with it.
  No distribution Snapper integration is removed. Snapshots on the source disk
  are not independent backups; system rollback remains the snapshot manager's UI.
- Indexing is opt in and bounded, not a claim to have exhaustively indexed every
  filesystem. Recent-file privacy filters apply to the configured exclusions.

## Verification

- Full automatic suite: 268 tests passed (213 seconds). Native C++ build,
  gettext validation and whitespace checks pass.
- Private-bus daemon tests cover file search, Unicode input, Fcitx/OSK, autostart
  preservation, file-copy collision protection, OBEX progress, external producer
  lifecycle, journal persistence and diagnostics export.
- Actual AppArmor parser and package backend tests use isolated namespaces; no
  user packages or real profiles are removed/changed by tests.
- Graphical regression runs in a nested compositor and includes AppInfo, all new
  settings pages, expanded input cards, narrow layouts, reduced motion, automatic
  operations indicator and popup. Host compositor/plugins are never hot-reloaded.
- Restic and GNOME Keyring tests run on their own D-Bus session, temporary home,
  keyring and repository; the real minute scheduler was verified to create a
  successful backup. Native application recovery uses only fixture windows.
- The staged daemon also passes isolated service tests while using the bundled
  Qt runtime and SQL driver; Qt Concurrent/SQL are included in that runtime.

Primary references checked during implementation:

- [Secret Service API](https://specifications.freedesktop.org/secret-service/latest-single/)
- [Flatpak permission store](https://github.com/flatpak/xdg-desktop-portal/wiki/The-Permission-Store)
- [Flatseal permission-to-override mapping](https://github.com/tchx84/Flatseal/blob/master/DOCUMENTATION.md)
- [Restic restoration and overwrite modes](https://github.com/restic/restic/blob/master/doc/050_restore.rst)
- [Hyprland 0.56.2 native ANR manager](https://github.com/hyprwm/Hyprland/blob/v0.56.2/src/managers/ANRManager.cpp)

## Settings navigation refactor (package 58)

The sidebar now contains ten top-level entries: Home, System, Bluetooth & devices,
Network & internet, Personalisation, Applications, Time & language, Accessibility,
Privacy & security, Maintenance & help. Individual tools are grouped inside their
section, rather than appended to the sidebar. Network and Accessibility open
straight to their functional pages. Permissions are managed from the installed
application; Privacy links to that same entry rather than duplicating the editor.

The common PageBase provides breadcrumbs and the existing themed header. Shared
navigation cards, hover/press feedback and reduced-motion-aware transitions reuse
hics tokens and components. Home offers common actions and category cards. Narrow
windows use a collapsible icon rail with tooltips; Ctrl+F/Ctrl+E opens search.
Backup and indexing limits/schedules are in animated advanced expanders.

Page indices and existing alias routes remain stable for search and external
widgets. History records section/page/detail routes; deferred construction is
coalesced, and obsolete StackPages cannot consume another page's navigation
signals. Graphical coverage checks every section, back navigation, same-index
routes, cross-page detail routes, narrow layouts and existing settings pages.
Native desktop workers also exit when their session bus disappears, avoiding
orphan workers after isolated/nested sessions end.

Design references: [Windows Settings navigation](https://support.microsoft.com/en-us/windows/experience/exploring-windows-settings),
[Microsoft settings card guidance](https://learn.microsoft.com/en-us/windows/apps/design/app-settings/guidelines-for-app-settings),
[hierarchical navigation and breadcrumbs](https://learn.microsoft.com/en-us/windows/apps/design/basics/navigation-basics).
