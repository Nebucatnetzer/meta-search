{
  inputs = {
    flake-parts.url = "github:hercules-ci/flake-parts";
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
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
        flake = {
          # Put your original flake attributes here.
        };
        systems = [
          # systems for which you want to build the `perSystem` attributes
          "aarch64-linux"
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
            nginxConfig = pkgs.writeText "nginx.conf" ''
              user nobody nobody;
              daemon off;
              error_log /dev/stdout info;
              pid /dev/null;
              events {}
              http {
                  types_hash_max_size 4096;
                  include ${pkgs.mailcap}/etc/nginx/mime.types;
                  upstream app {
                      server app:8000;
                  }

                  server {
                      listen 80;
                      location / {
                          proxy_pass http://app;
                          proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
                          proxy_set_header Host $host;
                          proxy_redirect off;
                      }

                      location /static/ {
                          alias /var/lib/zweili_search/static/;
                      }
                  }
              }
            '';
            pyproject = pkgs.lib.importTOML ./pyproject.toml;
            myPython = pkgs.python312.override {
              self = myPython;
              packageOverrides = pyfinal: pyprev: {
                zweili-search = pyfinal.buildPythonPackage {
                  pname = "zweili-search";
                  inherit (pyproject.project) version;
                  pyproject = true;
                  src = ./.;
                  propagatedBuildInputs = [ pyfinal.hatchling ];

                };
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
              p.beautifulsoup4
              p.django
              p.django-types
              p.gunicorn
              p.zweili-search-editable
              p.mypy
              p.pylsp-mypy
              p.pytest
              p.pytest-cov
              p.pytest-xdist
              p.python-lsp-server
              p.python-lsp-ruff
              p.requests
              p.ruff
              p.types-beautifulsoup4
            ]);
            pythonProd = myPython.withPackages (p: [
              p.beautifulsoup4
              p.django
              p.gunicorn
              p.requests
              p.zweili-search
            ]);
          in
          {
            packages = {
              inherit pythonProd;
              ci-tools = pkgs.buildEnv {
                name = "ci-tools";
                paths = [
                  pkgs.skopeo
                  pkgs.manifest-tool
                ];
                pathsToLink = [ "/bin" ];
              };
              app-image = pkgs.dockerTools.buildImage {
                name = "zweili-search-app";
                tag = "latest";
                architecture = "linux/arm64";
                copyToRoot = pkgs.buildEnv {
                  name = "image-root";
                  paths = [
                    pythonProd
                    (pkgs.writeShellScriptBin "start-app" ''
                      if [ -f /var/lib/zweili_search/first_run ]; then
                          ${pythonProd.interpreter} -m django collectstatic --noinput
                          ${pythonProd.interpreter} -m django migrate
                      else
                          ${pythonProd.interpreter} -m django collectstatic --noinput
                          ${pythonProd.interpreter} -m django migrate
                          ${pythonProd.interpreter} -m django shell < ${./tooling/bin/create_admin.py}
                          ${pythonProd.interpreter} -c "from pathlib import Path; Path('/var/lib/zweili_search/first_run').touch()"
                      fi
                      ${pythonProd.interpreter} -m gunicorn zweili_search.wsgi:application --reload --bind 0.0.0.0:8000 --workers 3
                    '')

                  ];
                };
                config = {
                  Cmd = [ "start-app" ];
                  Env = [
                    "DJANGO_SETTINGS_MODULE=zweili_search.settings"
                  ];
                  ExposedPorts = {
                    "8000/tcp" = { };
                  };
                };
              };
              nginx-image = pkgs.dockerTools.buildLayeredImage {
                name = "zweili-search-nginx";
                tag = "latest";
                contents = [
                  pkgs.fakeNss
                  pkgs.nginx
                ];

                extraCommands = ''
                  mkdir -p tmp/nginx_client_body

                  # nginx still tries to read this directory even if error_log
                  # directive is specifying another file :/
                  mkdir -p var/log/nginx
                '';

                config = {
                  Cmd = [
                    "nginx"
                    "-c"
                    nginxConfig
                  ];
                  ExposedPorts = {
                    "80/tcp" = { };
                  };
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
                ZWEILI_SEARCH_DB_DIR="$DEVENV_STATE"
                export ZWEILI_SEARCH_DB_DIR
                ZWEILI_STATIC_ROOT="$DEVENV_STATE"
                export ZWEILI_STATIC_ROOT
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
                    pkgs.nodePackages.prettier
                    pkgs.nixfmt-rfc-style
                    pkgs.shellcheck
                    pkgs.shfmt
                    pkgs.skopeo
                  ];
                  pathsToLink = [ "/bin" ];
                })
                pythonDev
              ];
            };
          };
      }
    );
}
