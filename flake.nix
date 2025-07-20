{
  inputs = {
    flake-parts.url = "github:hercules-ci/flake-parts";
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    process-compose-flake.url = "github:Platonic-Systems/process-compose-flake";
    services-flake.url = "github:juspay/services-flake";
  };

  outputs =
    {
      self,
      flake-parts,
      ...
    }@inputs:
    flake-parts.lib.mkFlake { inherit inputs self; } (
      top@{ ... }:
      {
        imports = [
          inputs.process-compose-flake.flakeModule
        ];
        flake = {
          # Put your original flake attributes here.
        };
        systems = [
          # systems for which you want to build the `perSystem` attributes
          "x86_64-linux"
          # ...
        ];
        perSystem =
          {
            config,
            pkgs,
            ...
          }:
          let
            pyproject = pkgs.lib.importTOML ./pyproject.toml;
            myPython = pkgs.python312.override {
              self = myPython;
              packageOverrides = pyfinal: pyprev: {
                # An editable package with a script that loads our mutable location
                zweili-search-editable = pyfinal.mkPythonEditablePackage {
                  # Inherit project metadata from pyproject.toml
                  pname = pyproject.project.name;
                  inherit (pyproject.project) version;

                  # The editable root passed as a string
                  root = "$DEVENV_ROOT/src"; # Use environment variable expansion at runtime
                };
              };
            };

            pythonDev = myPython.withPackages (p: [
              p.django
              p.django-types
              p.gunicorn
              p.zweili-search-editable
              p.mypy
              p.pylint
              p.pylsp-mypy
              p.pytest
              p.pytest-cov
              p.pytest-xdist
              p.python-lsp-server
            ]);
            pythonProd = myPython.withPackages (p: [
              p.django
              p.gunicorn
            ]);
          in
          {
            process-compose."dev-services" = {
              imports = [
                inputs.services-flake.processComposeModules.default
                {
                  settings.processes.django = {
                    command = ''
                      cd "$DEVENV_ROOT/src"
                      ${pythonDev}/bin/python manage.py runserver
                    '';
                  };
                }
              ];
            };
            packages = {
              inherit pkgs;
              zweili_search-image = pkgs.dockerTools.buildImage {
                name = "zweili-metasearch";
                tag = "latest";
                copyToRoot = pkgs.buildEnv {
                  name = "image-root";
                  paths = [
                    pythonProd
                    self
                  ];
                };
                config = {
                  Cmd = [
                    "${pythonProd}/bin/gunicorn"
                    "--bind=0.0.0.0"
                    "zweili_search.main:app"
                  ];
                };
              };
            };
            devShells.default = pkgs.mkShell {
              shellHook = ''
                DEVENV_ROOT="$PWD"
                export DEVENV_ROOT
                DEVENV_STATE="$DEVENV_ROOT/.devenv/state"
                export DEVENV_STATE
                mkdir -p "$DEVENV_STATE"
                PATH="$DEVENV_ROOT/tooling/bin:$PATH"
                export PATH
              '';
              env = {
                DEBUG = "True";
                NO_SSL = "True";
                PC_PORT_NUM = "9999";
              };
              packages = [
                (pkgs.buildEnv {
                  name = "zweili-metasearch-devShell";
                  paths = [
                    pkgs.black
                    pkgs.isort
                    pkgs.nodePackages.prettier
                    pkgs.nixfmt-rfc-style
                    pkgs.shellcheck
                    pkgs.shfmt
                  ];
                  pathsToLink = [ "/bin" ];
                })
                pythonDev
              ];
              inputsFrom = [
                config.process-compose."dev-services".services.outputs.devShell
              ];
            };
          };
      }
    );
}
