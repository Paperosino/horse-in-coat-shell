{ lib, stdenv, cmake, ninja, pkg-config, gettext, makeWrapper, qt6
, hyprland, quickshell, python3, libqalculate, lm_sensors, pixman, libdrm
, glib, libsecret, cups, util-linux, e2fsprogs, lua5_4, hyprgraphics, libinput, systemd, wayland, libxkbcommon, pango, cairo, nlohmann_json
, kitty, firefox, fuzzel, btop, pavucontrol, wl-clipboard, cliphist
, grim, slurp, wf-recorder, swappy, libnotify, brightnessctl, networkmanager
, pipewire, pulseaudio, wireplumber, polkit, hyprlock, hyprpicker, xdg-utils, xdg-user-dirs
, libxml2, adwaita-icon-theme, xkeyboard_config, src
}:
let
  python = python3.withPackages (packages: [ packages.pillow ]);
  runtime = [ glib quickshell hyprland python kitty firefox fuzzel btop pavucontrol
    wl-clipboard cliphist grim slurp wf-recorder swappy libnotify brightnessctl
    networkmanager pipewire pulseaudio wireplumber polkit hyprlock hyprpicker xdg-utils
    xdg-user-dirs libxml2 systemd libqalculate ];
in
assert lib.assertMsg (hyprland.version == "0.56.2") "Hyprstack requires Hyprland 0.56.2";
assert lib.assertMsg (lib.versionAtLeast quickshell.version "0.3.1") "Hyprstack requires Quickshell >= 0.3.1";
assert lib.assertMsg (lib.versionAtLeast qt6.qtbase.version "6.9") "Hyprstack requires Qt >= 6.9";
(hyprland.stdenv or stdenv).mkDerivation {
  pname = "hic-shell";
  version = "1.1.1";
  inherit src;

  nativeBuildInputs = [ cmake ninja pkg-config gettext makeWrapper qt6.wrapQtAppsHook python hyprland ];
  buildInputs = [ qt6.qtbase qt6.qtdeclarative qt6.qtshadertools qt6.qtmultimedia libqalculate lm_sensors networkmanager libsecret
    hyprland.dev cups util-linux e2fsprogs lua5_4 hyprgraphics pixman libdrm libinput systemd wayland libxkbcommon pango cairo nlohmann_json ]
    ++ (hyprland.buildInputs or []);

  cmakeBuildType = "Release";
  cmakeFlags = [
    "-DHYPRSTACK_BUILD_NATIVE=ON"
    "-DHYPRSTACK_BUILD_CANVAS=ON"
    "-DHYPRSTACK_AUDIO_VISUALIZER=OFF"
    "-DCMAKE_INSTALL_DATADIR=${builtins.placeholder "out"}/share"
  ];
  dontWrapQtApps = true;

  preConfigure = ''
    export XDG_RUNTIME_DIR="$TMPDIR/hics-runtime"
    mkdir -p "$XDG_RUNTIME_DIR"
    chmod 700 "$XDG_RUNTIME_DIR"
  '';

  postInstall = ''
    for program in hics-shell hics-session hics-session-runner hics-doctor hics-workspace; do
      wrapProgram "$out/bin/$program" \
        --set HYPRSTACK_DATA_DIR "$out/share/hics" \
        --set HYPRSTACK_TITLEBAR_PLUGIN "$out/share/hics/native/hics-bars.so" \
        --set HYPRSTACK_XKB_RULES_PATH "${xkeyboard_config}/share/X11/xkb/rules/base.lst" \
        --set-default HYPRSTACK_PAM_SERVICE hyprlock \
        --prefix PATH : "$out/bin:${lib.makeBinPath runtime}" \
        --prefix XDG_DATA_DIRS : "${adwaita-icon-theme}/share" \
        "''${qtWrapperArgs[@]}"
    done
  '';

  passthru = { inherit hyprland quickshell; };
  meta = {
    description = "Hyprstack desktop shell for Hyprland 0.56.2";
    homepage = "https://github.com/Paperosino/horse-in-coat-shell";
    license = lib.licenses.gpl3Only;
    platforms = [ "x86_64-linux" "aarch64-linux" ];
    mainProgram = "hics-shell";
  };
}
