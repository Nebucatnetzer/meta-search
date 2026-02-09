{
  myPython,
  pkgs,
}:
let
  pythonProd = myPython.withPackages (p: [
    p.django
    p.gunicorn
    p.whitenoise
    p.zweili-search
  ]);
in
{
  inherit pythonProd;
  ci-tools = pkgs.callPackage ./ci_tools.nix { };
  app-image = pkgs.callPackage ./app { inherit pythonProd; };
}
