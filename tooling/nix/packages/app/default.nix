{
  buildEnv,
  dockerTools,
  myPython,
}:
let
  pythonRuntime = myPython.withPackages (p: [ p.zweili-search ]);
in
dockerTools.buildImage {
  name = "zweili-search-app";
  tag = "latest";
  architecture = "amd64";
  copyToRoot = buildEnv {
    name = "image-root";
    paths = [
      pythonRuntime
      myPython.pkgs.zweili-search
    ];
  };
  config = {
    Cmd = [
      "${pythonRuntime.interpreter}"
      ./docker-cmd.py
    ];
    Env = [
      "DJANGO_SETTINGS_MODULE=zweili_search.settings"
    ];
    ExposedPorts = {
      "8000/tcp" = { };
    };
  };
}
