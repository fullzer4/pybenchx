{
  inputs.nixpkgs.url       = "github:NixOS/nixpkgs/nixos-unstable";
  inputs.nixpkgs_py37.url  = "github:NixOS/nixpkgs/nixos-21.11";
  inputs.nixpkgs_py38.url  = "github:NixOS/nixpkgs/nixos-22.11";
  inputs.nixpkgs_py39.url  = "github:NixOS/nixpkgs/nixos-23.11";

  outputs = { self, nixpkgs, nixpkgs_py37, nixpkgs_py38, nixpkgs_py39 }:
    let
      systems = [ "x86_64-linux" "aarch64-linux" "x86_64-darwin" "aarch64-darwin" ];
      forAll  = nixpkgs.lib.genAttrs systems;

      pkgsFor = system: import nixpkgs { inherit system; config.allowUnfree = true; };

      pkgs37For = system: import nixpkgs_py37 { inherit system; config.allowUnfree = true; };
      pkgs38For = system: import nixpkgs_py38 { inherit system; config.allowUnfree = true; };
      pkgs39For = system: import nixpkgs_py39 { inherit system; config.allowUnfree = true; };

      mkShell = { pkgs, python, extras ? [ ] }:
        pkgs.mkShell {
          packages  = [ python ] ++ extras;
          shellHook = ''
            echo ">> pybenchx devshell — Python: $(${python.interpreter} -V)"
          '';
        };

      hasAttr = set: attr: builtins.hasAttr attr set;

    in {
      formatter = forAll (system: (pkgsFor system).nixfmt);

      devShells = forAll (system:
        let
          pkgs    = pkgsFor system;
          pkgs37  = pkgs37For system;
          pkgs38  = pkgs38For system;
          pkgs39  = pkgs39For system;

          have37 = hasAttr pkgs37 "python37";
          have38 = hasAttr pkgs38 "python38";
          have39 = hasAttr pkgs39 "python39";
        in {
          # default = 3.12
          default = mkShell {
            pkgs   = pkgs;
            python = pkgs.python312.withPackages (p: [ p.pytest ]);
            extras = [ pkgs.uv pkgs.pkg-config pkgs.ripgrep ];
          };

          py310 = mkShell {
            pkgs   = pkgs;
            python = pkgs.python310.withPackages (p: [ p.pytest ]);
            extras = [ pkgs.uv pkgs.pkg-config pkgs.ripgrep ];
          };

          py311 = mkShell {
            pkgs   = pkgs;
            python = pkgs.python311.withPackages (p: [ p.pytest ]);
            extras = [ pkgs.uv pkgs.pkg-config pkgs.ripgrep ];
          };

          py312 = mkShell {
            pkgs   = pkgs;
            python = pkgs.python312.withPackages (p: [ p.pytest ]);
            extras = [ pkgs.uv pkgs.pkg-config pkgs.ripgrep ];
          };

          py313 = mkShell {
            pkgs   = pkgs;
            python = pkgs.python313.withPackages (p: [ p.pytest ]);
            extras = [ pkgs.uv pkgs.pkg-config pkgs.ripgrep ];
          };

          py39 = if have39 then
            mkShell {
              pkgs   = pkgs;
              python = pkgs39.python39.withPackages (p: [ p.pytest ]);
              extras = [ pkgs.uv pkgs.pkg-config pkgs.ripgrep ];
            }
          else pkgs.mkShell {
            packages  = [ pkgs.pkg-config pkgs.ripgrep ];
            shellHook = "echo '!! python39 not available on ${system} for nixpkgs 23.11'";
          };

          py38 = if have38 then
            mkShell {
              pkgs   = pkgs;
              python = pkgs38.python38.withPackages (p: [ p.pytest ]);
              extras = [ pkgs.uv pkgs.pkg-config pkgs.ripgrep ];
            }
          else pkgs.mkShell {
            packages  = [ pkgs.pkg-config pkgs.ripgrep ];
            shellHook = "echo '!! python38 not available on ${system} for nixpkgs 22.11'";
          };

          py37 = if have37 then
            mkShell {
              pkgs   = pkgs;
              python = pkgs37.python37.withPackages (p: [ p.pytest p.pip p.setuptools p.wheel ]);
              extras = [ pkgs.pkg-config pkgs.ripgrep ];
            }
          else pkgs.mkShell {
            packages  = [ pkgs.pkg-config pkgs.ripgrep ];
            shellHook = "echo '!! python37 not available on ${system} for nixpkgs 21.11'";
          };

          docs = pkgs.mkShell {
            packages = [ pkgs.nodejs_20 pkgs.ripgrep ];
            shellHook = ''
              echo ">> docs devshell — Node: $(node -v), npm: $(npm -v)"
              echo "Run: cd docs && npm install && npm run dev"
            '';
          };
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
          build   = { type = "app"; program = "${buildScript}"; };
          publish = { type = "app"; program = "${publishScript}"; };
        });
    };
}
