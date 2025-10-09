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
            pkgs,
            ...
          }:
          let
            nginxConfig = pkgs.writeText "nginx.conf" ''
              user nobody nobody;
              daemon off;
              error_log /dev/stdout info;
              pid /dev/null;
              worker_processes auto;
              events {}
              http {
                  types_hash_max_size 4096;
                  include ${pkgs.mailcap}/etc/nginx/mime.types;
                  upstream app {
                      server zweili-search-app:8000;
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
                          alias ${staticFiles}/static/;
                      }
                  }
              }
            '';
            pyproject = pkgs.lib.importTOML ./pyproject.toml;
            myPython = pkgs.python312.override {
              self = myPython;
              packageOverrides = pyfinal: pyprev: {
                types-gevent = (
                  let
                    version = "25.4.0.20250915";
                  in
                  pyfinal.buildPythonPackage {
                    inherit version;
                    pname = "types-gevent";
                    pyproject = true;
                    dependencies = [
                      pyfinal.types-psutil
                      pyfinal.types-greenlet
                    ];
                    src = pkgs.fetchPypi {
                      inherit version;
                      pname = "types_gevent";
                      hash = "sha256-loH13MxrHypgxybaPEhJSmqm8OBaY4/fsM+UThOoJlo=";
                    };
                    build-system = [ pyfinal.setuptools ];
                    doCheck = false;
                    pythonImportsCheck = [ "gevent-stubs" ];
                  }
                );
                types-gunicorn = (
                  let
                    version = "23.0.0.20251001";
                  in
                  pyfinal.buildPythonPackage {
                    inherit version;
                    pname = "types-gunicorn";
                    pyproject = true;
                    dependencies = [ pyfinal.types-gevent ];
                    src = pkgs.fetchPypi {
                      inherit version;
                      pname = "types_gunicorn";
                      hash = "sha256-NG8o5K5S+nQBJiR/V1oGLW6XgcoG0iaQUP/8hopsAu0=";
                    };
                    build-system = [ pyfinal.setuptools ];
                    doCheck = false;
                    pythonImportsCheck = [ "gunicorn-stubs" ];
                  }
                );
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
              p.docformatter
              p.gunicorn
              p.zweili-search-editable
              p.mypy
              p.playwright
              p.pylint
              p.pylsp-mypy
              p.pytest
              p.pytest-cov
              p.pytest-django
              p.pytest-xdist
              p.python-lsp-server
              p.python-lsp-ruff
              p.requests
              p.ruff
              p.types-beautifulsoup4
              p.types-gunicorn
              p.types-requests
            ]);
            pythonProd = myPython.withPackages (p: [
              p.beautifulsoup4
              p.django
              p.gunicorn
              p.playwright
              p.requests
              p.zweili-search
            ]);
            staticFiles = pkgs.stdenv.mkDerivation {
              pname = "${pyproject.project.name}-static";
              version = pyproject.project.version;
              src = ./.;
              buildPhase = ''
                export ZWEILI_SEARCH_DB_DIR="$out"
                export DJANGO_SETTINGS_MODULE=zweili_search.settings
                export MEDIA_ROOT=/dev/null
                export SECRET_KEY=dummy
                export DATABASE_URL=sqlite://:memory:
                ${pythonProd.interpreter} -m django collectstatic --noinput
              '';
              phases = [ "buildPhase" ];
            };
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
                  ];
                };
                config = {
                  Cmd = [
                    "${pythonProd.interpreter}"
                    ./docker-cmd.py
                  ];
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
                PLAYWRIGHT_BROWSERS_PATH = "${pkgs.playwright.browsers}";
              };
              packages = [
                (pkgs.buildEnv {
                  name = "zweili-metasearch-devShell";
                  paths = [
                    pkgs.black
                    pkgs.chromium
                    pkgs.isort
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
