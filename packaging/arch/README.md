# Arch package

`build-package.sh` stages the repository tree, resolves build dependencies
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
- If `sudo` needs a password, the script prints the exact `pacman -U` command
  instead of installing.
- Updating the package rebuilds the bundled runtime against the then-current
  system Qt; see `MAINTENANCE.md`.

After installation and upgrades, the package reloads running systemd user
managers and restarts active `hic-session.service` instances automatically.
Inactive shells stay inactive. Hyprland and applications remain running.
If a user manager cannot be reached, the installer prints a warning and
continues with other users; run `hics-session restart` in that session.
