self: { config, lib, pkgs, ... }:
let
  cfg = config.programs.hics;
  package = cfg.package;
in {
  options.programs.hics = {
    enable = lib.mkEnableOption "Hyprstack and its matching Hyprland session";
    package = lib.mkOption {
      type = lib.types.package;
      default = self.packages.${pkgs.stdenv.hostPlatform.system}.default;
      description = "Hyprstack package, including its matching compositor and Quickshell.";
    };
  };

  config = lib.mkIf cfg.enable {
    assertions = [{
      assertion = toString config.programs.hyprland.package == toString package.hyprland;
      message = "Hyprstack's native module must use the same Hyprland package as the system session.";
    }];

    programs.hyprland.enable = true;
    programs.hyprland.package = lib.mkDefault package.hyprland;
    programs.hyprlock.enable = true;
    environment.systemPackages = [ package ];
    environment.sessionVariables = {
      HYPRSTACK_DATA_DIR = "${package}/share/hics";
      HYPRSTACK_SESSION_COMMAND = "${package}/bin/hics-session";
    };

    services.dbus.packages = [ package ];
    security.polkit.enable = true;
    # Use the existing Secret Service/PAM integration rather than a second vault.
    services.gnome.gnome-keyring.enable = lib.mkDefault true;
    systemd.packages = [ package ];

    systemd.user.services.hic-session = {
      description = "Hyprstack desktop session";
      partOf = [ "graphical-session.target" ];
      unitConfig.ConditionEnvironment = "HYPRLAND_INSTANCE_SIGNATURE";
      serviceConfig = {
        Type = "simple";
        ExecStart = "${package}/bin/hics-session-runner";
        Restart = "on-failure";
        RestartSec = 3;
        TimeoutStopSec = 10;
        KillMode = "process";
      };
    };
  };
}
