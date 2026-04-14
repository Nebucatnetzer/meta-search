{
  myPython,
  pkgs,
}:
let
  app-image = pkgs.callPackage ./app { inherit myPython; };
in
{
  ci-tools = pkgs.callPackage ./ci_tools.nix { };
  default = app-image;
  inherit app-image;
}
