{ myPython, pkgs }:
let
  pythonDev = myPython.withPackages (p: [
    p.beautifulsoup4
    p.black
    p.django
    p.django-types
    p.docformatter
    p.gunicorn
    p.isort
    p.mypy
    p.pylint
    p.pylint-django
    p.pylsp-mypy
    p.pytest
    p.pytest-cov
    p.pytest-django
    p.pytest-xdist
    p.python-lsp-ruff
    p.python-lsp-server
    p.requests
    p.types-beautifulsoup4
    p.types-requests
    p.vulture
    p.zweili-search-editable
  ]);
in
pkgs.mkShell {
  shellHook = builtins.readFile ./shell_hook.sh;
  packages = [
    (pkgs.buildEnv {
      name = "zweili-metasearch-devShell";
      paths = [
        pkgs.deadnix
        pkgs.nodePackages.prettier
        pkgs.nixfmt-rfc-style
        pkgs.ruff
        pkgs.shellcheck
        pkgs.shfmt
        pkgs.skopeo
      ];
      pathsToLink = [ "/bin" ];
    })
    pythonDev
  ];
}
