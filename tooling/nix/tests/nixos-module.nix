{ self }:
{
  name = "zweili-search";
  nodes.machine =
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
  testScript = ''
    machine.wait_for_unit("zweili-search.service")
    machine.wait_for_open_port(8000)
    machine.succeed("curl --fail --silent --header 'Host: search.example.org' http://127.0.0.1:8000/accounts/login/ | grep --quiet csrfmiddlewaretoken")
    machine.succeed("curl --fail --silent --head http://127.0.0.1:8000/static/vendor/pico/pico.min.css")
    machine.succeed("zweili-search-manage check --deploy --fail-level ERROR")
    machine.succeed("test \"$(stat --format=%U /var/lib/zweili_search/db.sqlite3)\" = zweili-search")
  '';
}
