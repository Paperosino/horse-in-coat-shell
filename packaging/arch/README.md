# Arch package

`build-package.sh` stages the repository tree, resolves runtime and build dependencies
via pacman and runs `makepkg`. The produced package bundles its own pinned
quickshell (v0.3.2) and a private Qt runtime under `/usr/share/hics/qs`,
so system quickshell/Qt updates cannot break the shell.

```bash
packaging/arch/build-package.sh            # build only
packaging/arch/build-package.sh --install  # build and install via pacman -U
```

Notes:

- The built package is copied to the repository root; `KEEP_STAGING=1` keeps
  the temporary build directory for inspection.
- `sudo` prompts for a password normally; installation failures are reported
  as failures, while the built artifact remains available.
- Updating the package rebuilds the bundled runtime against the then-current
  system Qt; see `MAINTENANCE.md`.

After installation and upgrades, the package reloads running systemd user
managers and activates/restarts `hic-session`, `hics-desktop`, `hics-displays`
and `hics-configuration` services in live Hyprland sessions automatically.
Inactive shells in TTY/expired sessions stay inactive; a live Hyprland session
starts all four hics user services on first installation. Hyprland and applications remain running.
If a user manager cannot be reached, the installer prints a warning and
continues with other users; run `hics-session restart` in that session.

Secrets use `libsecret` and the user's existing Secret Service. `gnome-keyring`
is a required runtime dependency, providing a default service on fresh installs.
The package does not replace an active provider, migrate collections, reset a
master password, or modify the distribution's PAM configuration. Automatic
unlocking depends on the login manager's PAM stack and matching login/keyring
passwords; passwordless/autologin sessions may require a separate unlock prompt.


From the repository root, `./install.sh` builds and installs everything required.
`./install.sh --package FILE` installs a prebuilt package and runtime dependencies.
`./install.sh --dry-run` checks dependencies without installing or building.
Optional integrations from `optdepends` are not installed indiscriminately.
Persistent unit enabling also works offline; daemon activation requires a running
system manager. `hics-session start` imports the compositor environment and starts
its helper services idempotently. The screen reader is controlled by accessibility
settings.
