{ self }:
let
  baseConfig =
    { pkgs, ... }:
    {
      imports = [ self.nixosModules.default ];
      environment.systemPackages = [ pkgs.curl ];
      services.zweili-search = {
        enable = true;
        domain = "search.example.org";
        environmentFile = toString (pkgs.writeText "zweili-search.env" "SECRET_KEY=test-only");
        workers = 2;
      };
    };
in
{
  name = "zweili-search";
  nodes.standard = baseConfig;
  nodes.custom = {
    imports = [ baseConfig ];
    services.zweili-search.stateDir = "/srv/zweili-search";
  };
  testScript = ''
    start_all()
    for node, state_dir in [(standard, "/var/lib/zweili_search"), (custom, "/srv/zweili-search")]:
        node.wait_for_unit("zweili-search.service")
        node.wait_for_open_port(8000)
        node.succeed("curl --fail --silent --header 'Host: search.example.org' http://127.0.0.1:8000/accounts/login/ | grep --quiet csrfmiddlewaretoken")
        node.succeed("curl --fail --silent --head http://127.0.0.1:8000/static/vendor/pico/pico.min.css")
        node.succeed("zweili-search-manage check --deploy --fail-level ERROR")
        node.succeed(f"test \"$(stat --format=%U:%a {state_dir})\" = zweili-search:750")
        node.succeed(f"test \"$(stat --format=%U {state_dir}/db.sqlite3)\" = zweili-search")
  '';
}
