{
  dockerTools,
  fakeNss,
  mailcap,
  nginx,
  pyproject,
  pythonProd,
  root,
  stdenv,
  writeText,
}:
let
  nginxConfig = writeText "nginx.conf" ''
    user nobody nobody;
    daemon off;
    error_log /dev/stdout info;
    pid /dev/null;
    worker_processes auto;
    events {}
    http {
        types_hash_max_size 4096;
        include ${mailcap}/etc/nginx/mime.types;
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
  staticFiles = stdenv.mkDerivation {
    pname = "${pyproject.project.name}-static";
    version = pyproject.project.version;
    src = root;
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
dockerTools.buildLayeredImage {
  name = "zweili-search-nginx";
  tag = "latest";
  contents = [
    fakeNss
    nginx
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
}
