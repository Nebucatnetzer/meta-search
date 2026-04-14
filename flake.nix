{
  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-25.11";
  };
  outputs =
    { ... }@inputs:
    let
      system = "x86_64-linux";
      pkgs = inputs.nixpkgs.legacyPackages."${system}";
      pyproject = pkgs.lib.importTOML ./pyproject.toml;
      myPython = pkgs.python3.override {
        self = myPython;
        packageOverrides = pyfinal: _: {
          zweili-search = pyfinal.buildPythonPackage {
            pname = "zweili-search";
            inherit (pyproject.project) version;
            pyproject = true;
            src = root;
            buildInputs = [ pyfinal.hatchling ];
            propagatedBuildInputs = [
              pyfinal.django
              pyfinal.gunicorn
              pyfinal.whitenoise
            ];
            postInstall = ''
              export ZWEILI_SEARCH_DB_DIR="$out"
              export DJANGO_SETTINGS_MODULE=zweili_search.settings
              export MEDIA_ROOT=/dev/null
              export SECRET_KEY=dummy
              export DATABASE_URL=sqlite://:memory:
              ${myPython.interpreter} -m django collectstatic --noinput
            '';
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
      root = ./.;
    in
    {
      packages."${system}" = import ./tooling/nix/packages {
        inherit
          myPython
          pkgs
          ;
      };
      devShells."${system}".default = import ./tooling/nix/dev_shell { inherit myPython pkgs; };
    };
}
