{
  buildEnv,
  dockerTools,
  lib,
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
    ];
  };
  config = {
    Cmd = [ (lib.getExe myPython.pkgs.zweili-search) ];
    Env = [
      "DJANGO_SETTINGS_MODULE=zweili_search.settings"
      "ZWEILI_SEARCH_CREATE_DEFAULT_ADMIN=true"
    ];
    ExposedPorts = {
      "8000/tcp" = { };
    };
  };
}
