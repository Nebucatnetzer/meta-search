{
  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-26.05";
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
          zweili-search = pyfinal.callPackage ./tooling/nix/packages/zweili-search.nix { };
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
    in
    {
      packages."${system}" = import ./tooling/nix/packages {
        inherit
          myPython
          pkgs
          ;
      };
      devShells."${system}".default = import ./tooling/nix/dev_shell { inherit myPython pkgs; };
      nixosModules.default = import ./tooling/nix/module.nix;
      checks."${system}".nixos-module = pkgs.testers.runNixOSTest (
        import ./tooling/nix/tests/nixos-module.nix { inherit (inputs) self; }
      );
    };
}
