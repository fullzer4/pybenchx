{
  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

  outputs = { self, nixpkgs }:
    let
      systems = [ "x86_64-linux" "aarch64-linux" "x86_64-darwin" "aarch64-darwin" ];
      forAll = nixpkgs.lib.genAttrs systems;
      pkgsFor = system: import nixpkgs { inherit system; config.allowUnfree = true; };

      mkShell = pkgs: python: pkgs.mkShell {
        packages = [ python pkgs.uv pkgs.pkg-config pkgs.ripgrep ];
        shellHook = ''
          echo ">> pybenchx devshell — Python: $(${python.interpreter} -V)"
        '';
      };
    in {
      formatter = forAll (system: (pkgsFor system).nixfmt);

      devShells = forAll (system:
        let pkgs = pkgsFor system; in {
          default = mkShell pkgs pkgs.python312;
          py310   = mkShell pkgs pkgs.python310;
          py311   = mkShell pkgs pkgs.python311;
          py312   = mkShell pkgs pkgs.python312;
          py313   = mkShell pkgs pkgs.python313;
        });

      apps = forAll (system:
        let
            pkgs = pkgsFor system;

            buildScript = pkgs.writeShellScript "pybenchx-build" ''
            set -euo pipefail
            ${pkgs.uv}/bin/uv --version
            ${pkgs.uv}/bin/uv build
            '';

            publishScript = pkgs.writeShellScript "pybenchx-publish" ''
            set -euo pipefail
            test -n "''${PYPI_TOKEN-}" || { echo "PYPI_TOKEN not set"; exit 1; }
            ${pkgs.uv}/bin/uv publish --token "$PYPI_TOKEN"
            '';
        in {
            build = { type = "app"; program = "${buildScript}"; };
            publish = { type = "app"; program = "${publishScript}"; };
        });
    };
}
