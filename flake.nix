{
  description = "Hyprstack shell and matching Hyprland integration";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/55bfb4d7437bd4e09ab7cba58a43bd68eb310044";

  outputs = { self, nixpkgs }:
    let
      systems = [ "x86_64-linux" "aarch64-linux" ];
      eachSystem = nixpkgs.lib.genAttrs systems;
    in {
      packages = eachSystem (system:
        let
          pkgs = nixpkgs.legacyPackages.${system};
          package = pkgs.callPackage ./nix/package.nix {
            src = pkgs.lib.fileset.toSource {
              root = ./.;
              fileset = pkgs.lib.fileset.unions [
                ./CMakeLists.txt ./LICENSE ./THIRD_PARTY.md
                ./shell ./native ./third_party ./distribution
              ];
            };
          };
        in {
          default = package;
          hyprstack = package;
          inherit (package) hyprland quickshell;
        });

      nixosModules.default = import ./nix/nixos-module.nix self;
      homeManagerModules.default = import ./nix/home-manager.nix self;
    };
}
