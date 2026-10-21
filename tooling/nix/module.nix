{
  config,
  lib,
  pkgs,
  ...
}:
let
  cfg = config.services.zweili-search;
  stateDirectory = "/var/lib/zweili_search";
  environment = {
    DJANGO_SETTINGS_MODULE = "zweili_search.settings";
    ZWEILI_SEARCH_BIND = "${cfg.listenAddress}:${toString cfg.port}";
    ZWEILI_SEARCH_DB_DIR = stateDirectory;
    ZWEILI_SEARCH_DOMAIN = cfg.domain;
  }
  // lib.optionalAttrs (cfg.workers != null) { ZWEILI_SEARCH_WORKERS = toString cfg.workers; };
  setenvArguments = lib.mapAttrsToList (
    name: value: "--setenv=${lib.escapeShellArg "${name}=${value}"}"
  ) environment;
  # Runs a Django management command as the service user, with the service environment.
  manage = pkgs.writeShellApplication {
    name = "zweili-search-manage";
    text = ''
      if [ -t 0 ]; then
        io_mode=--pty
      else
        io_mode=--pipe
      fi
      exec ${lib.getExe' config.systemd.package "systemd-run"} \
        "$io_mode" \
        --wait \
        --collect \
        --quiet \
        --uid=zweili-search \
        --gid=zweili-search \
        --working-directory=${stateDirectory} \
        --property=EnvironmentFile=${lib.escapeShellArg cfg.environmentFile} \
        ${lib.concatStringsSep " " setenvArguments} \
        ${lib.getExe' cfg.package "zweili-search-manage"} "$@"
    '';
  };
in
{
  options.services.zweili-search = {
    enable = lib.mkEnableOption "the zweili search bang service";
    package = lib.mkOption {
      type = lib.types.package;
      default = pkgs.python3Packages.callPackage ./packages/zweili-search.nix { };
      defaultText = lib.literalExpression "pkgs.python3Packages.callPackage ./packages/zweili-search.nix { }";
      description = "The package to run. The default builds it with the nixpkgs of the host.";
    };
    domain = lib.mkOption {
      type = lib.types.str;
      example = "search.example.org";
      description = "Public domain name. It is added to ALLOWED_HOSTS and CSRF_TRUSTED_ORIGINS.";
    };
    listenAddress = lib.mkOption {
      type = lib.types.str;
      default = "127.0.0.1";
      description = "Address for Gunicorn to listen on. Put a reverse proxy with TLS in front of it.";
    };
    port = lib.mkOption {
      type = lib.types.port;
      default = 8000;
      description = "Port for Gunicorn to listen on.";
    };
    workers = lib.mkOption {
      type = lib.types.nullOr lib.types.ints.positive;
      default = null;
      description = "Number of Gunicorn workers. Null means one more than the number of CPUs.";
    };
    environmentFile = lib.mkOption {
      type = lib.types.str;
      example = "/run/secrets/zweili-search.env";
      description = ''
        File that contains at least `SECRET_KEY=...`. systemd reads it as root.
        Use a string path outside the Nix store, for example from agenix or sops-nix.
      '';
    };
  };

  config = lib.mkIf cfg.enable {
    users.users.zweili-search = {
      isSystemUser = true;
      group = "zweili-search";
    };
    users.groups.zweili-search = { };

    environment.systemPackages = [ manage ];

    systemd.services.zweili-search = {
      description = "Zweili search";
      wantedBy = [ "multi-user.target" ];
      after = [ "network.target" ];
      inherit environment;
      serviceConfig = {
        ExecStart = lib.getExe cfg.package;
        EnvironmentFile = cfg.environmentFile;
        User = "zweili-search";
        Group = "zweili-search";
        StateDirectory = "zweili_search";
        StateDirectoryMode = "0750";
        WorkingDirectory = stateDirectory;
        Restart = "on-failure";

        CapabilityBoundingSet = "";
        LockPersonality = true;
        NoNewPrivileges = true;
        PrivateDevices = true;
        PrivateTmp = true;
        ProtectClock = true;
        ProtectControlGroups = true;
        ProtectHome = true;
        ProtectHostname = true;
        ProtectKernelLogs = true;
        ProtectKernelModules = true;
        ProtectKernelTunables = true;
        ProtectSystem = "strict";
        RestrictAddressFamilies = [
          "AF_INET"
          "AF_INET6"
          "AF_UNIX"
        ];
        RestrictNamespaces = true;
        RestrictRealtime = true;
        RestrictSUIDSGID = true;
        SystemCallArchitectures = "native";
        UMask = "0077";
      };
    };
  };
}
