self: { config, lib, pkgs, ... }:
let
  cfg = config.programs.hyprstack;
  package = cfg.package;
in {
  options.programs.hyprstack = {
    enable = lib.mkEnableOption "Hyprstack user configuration";
    package = lib.mkOption {
      type = lib.types.package;
      default = self.packages.${pkgs.stdenv.hostPlatform.system}.default;
      description = "Hyprstack package matching the system Hyprland package.";
    };
  };

  config = lib.mkIf cfg.enable {
    home.packages = [ package ];
    home.sessionVariables = {
      HYPRSTACK_DATA_DIR = "${package}/share/hyprstack";
      HYPRSTACK_SESSION_COMMAND = "${package}/bin/hyprstack-session";
    };
    xdg.configFile."hypr" = {
      source = "${package}/share/hyprstack/shell/assets/hyprland/config";
      recursive = true;
    };
    xdg.configFile."hyprstack/hypr-user.lua".source = "${package}/share/hyprstack/defaults/hyprstack/hypr-user.lua";

    # GUI-editable preferences stay ordinary user files. Only missing defaults
    # are created, so activation preserves monitor rules and local overrides.
    home.activation.hyprstackDefaults = lib.hm.dag.entryAfter [ "linkGeneration" ] ''
      run ${pkgs.python3}/bin/python3 - ${lib.escapeShellArg config.xdg.configHome} ${package} <<'PY'
      from pathlib import Path
      import shutil, sys
      config, package = map(Path, sys.argv[1:])
      target = config / "hyprstack"
      target.mkdir(parents=True, exist_ok=True)
      for source in (package / "share/hyprstack/defaults/hyprstack").iterdir():
          destination = target / source.name
          if not destination.exists() and not destination.is_symlink():
              shutil.copyfile(source, destination)
      PY
    '';
  };
}
