{
  config,
  lib,
  pkgs,
  ...
}:
let
  cfg = config.services.zweili-search;
  # systemd creates StateDirectory= only below /var/lib.
  useSystemdStateDirectory = lib.hasPrefix "/var/lib/" cfg.stateDir;
  environment = {
    DJANGO_SETTINGS_MODULE = "zweili_search.settings";
    ZWEILI_SEARCH_BIND = "${cfg.listenAddress}:${toString cfg.port}";
    ZWEILI_SEARCH_DB_DIR = cfg.stateDir;
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
        --working-directory=${lib.escapeShellArg cfg.stateDir} \
        --property=EnvironmentFile=${lib.escapeShellArg cfg.environmentFile} \
        ${lib.concatStringsSep " " setenvArguments} \
        ${lib.getExe' cfg.package "zweili-search-manage"} "$@"
    '';
  };
  # The setup service and the main service run as the same user with the same sandbox.
  commonServiceConfig = {
    EnvironmentFile = cfg.environmentFile;
    User = "zweili-search";
    Group = "zweili-search";
    StateDirectory = lib.mkIf useSystemdStateDirectory (lib.removePrefix "/var/lib/" cfg.stateDir);
    StateDirectoryMode = lib.mkIf useSystemdStateDirectory "0750";
    ReadWritePaths = lib.mkIf (!useSystemdStateDirectory) [ cfg.stateDir ];
    WorkingDirectory = cfg.stateDir;

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
    stateDir = lib.mkOption {
      type = lib.types.pathWith {
        inStore = false;
        absolute = true;
      };
      default = "/var/lib/zweili_search";
      example = "/srv/zweili-search";
      description = ''
        Directory for the SQLite database. Below /var/lib, systemd manages it with StateDirectory=.
        Other paths are created with tmpfiles and must not be under /home, /root or /run/user.
      '';
    };
    adminUsername = lib.mkOption {
      type = lib.types.str;
      default = "admin";
      description = ''
        Name of the admin user that zweili-search-setup.service creates if it does not exist.
        The new user gets the password `password`. Change it after the first login.
      '';
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

    systemd.tmpfiles.settings.zweili-search = lib.mkIf (!useSystemdStateDirectory) {
      ${cfg.stateDir}.d = {
        user = "zweili-search";
        group = "zweili-search";
        mode = "0750";
      };
    };

    environment.systemPackages = [ manage ];

    systemd.services.zweili-search = {
      description = "Zweili search";
      wantedBy = [ "multi-user.target" ];
      after = [ "network.target" ];
      inherit environment;
      serviceConfig = commonServiceConfig // {
        ExecStart = lib.getExe cfg.package;
        Restart = "on-failure";
      };
    };

    systemd.services.zweili-search-setup = {
      description = "Zweili search migrations and admin user";
      requiredBy = [ "zweili-search.service" ];
      before = [ "zweili-search.service" ];
      environment = environment // {
        ZWEILI_SEARCH_ADMIN_USERNAME = cfg.adminUsername;
      };
      serviceConfig = commonServiceConfig // {
        Type = "oneshot";
        RemainAfterExit = true;
        ExecStart = lib.getExe' cfg.package "zweili-search-setup";
      };
    };
  };
}
