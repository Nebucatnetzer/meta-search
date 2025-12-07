{
  buildEnv,
  dockerTools,
  pythonProd,
}:
dockerTools.buildImage {
  name = "zweili-search-app";
  tag = "latest";
  architecture = "linux/arm64";
  copyToRoot = buildEnv {
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
}
