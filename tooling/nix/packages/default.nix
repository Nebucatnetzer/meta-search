{
  myPython,
  pkgs,
  pyproject,
  root,
}:
let
  pythonProd = myPython.withPackages (p: [
    p.beautifulsoup4
    p.django
    p.gunicorn
    p.requests
    p.zweili-search
  ]);
in
{
  inherit pythonProd;
  ci-tools = pkgs.callPackage ./ci_tools.nix { };
  app-image = pkgs.callPackage ./app { inherit pythonProd; };
  nginx-image = pkgs.callPackage ./static_files.nix { inherit pythonProd pyproject root; };
}
