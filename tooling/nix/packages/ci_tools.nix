{
  buildEnv,
  manifest-tool,
  skopeo,
}:
buildEnv {
  name = "ci-tools";
  paths = [
    skopeo
    manifest-tool
  ];
  pathsToLink = [ "/bin" ];
}
