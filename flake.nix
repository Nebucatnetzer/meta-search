{
  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  };
  outputs =
    { ... }@inputs:
    let
      system = "x86_64-linux";
      pkgs = inputs.nixpkgs.legacyPackages."${system}";
      pyproject = pkgs.lib.importTOML ./pyproject.toml;
      myPython = pkgs.python312.override {
        self = myPython;
        packageOverrides = pyfinal: _: {
          zweili-search = pyfinal.buildPythonPackage {
            pname = "zweili-search";
            inherit (pyproject.project) version;
            pyproject = true;
            src = root;
            propagatedBuildInputs = [ pyfinal.hatchling ];
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
          pyproject
          root
          ;
      };
      packages."aarch64-linux" = import ./tooling/nix/packages {
        inherit
          myPython
          pkgs
          pyproject
          root
          ;
      };
      devShells."${system}".default = import ./tooling/nix/dev_shell { inherit myPython pkgs; };
    };
}
