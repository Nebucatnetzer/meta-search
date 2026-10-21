{
  buildPythonPackage,
  django,
  gunicorn,
  hatchling,
  lib,
  python,
  whitenoise,
}:
let
  root = ../../..;
  pyproject = lib.importTOML (root + "/pyproject.toml");
in
buildPythonPackage {
  pname = "zweili-search";
  inherit (pyproject.project) version;
  pyproject = true;
  # Only these files go into the build, so other changes do not cause a rebuild.
  src = lib.fileset.toSource {
    inherit root;
    fileset = lib.fileset.unions [
      (root + "/LICENSE")
      (root + "/README.org")
      (root + "/pyproject.toml")
      (root + "/src")
    ];
  };
  build-system = [ hatchling ];
  dependencies = [
    django
    gunicorn
    whitenoise
  ];
  postInstall = ''
    export ZWEILI_SEARCH_DB_DIR="$out"
    export DJANGO_SETTINGS_MODULE=zweili_search.settings
    export MEDIA_ROOT=/dev/null
    export SECRET_KEY=dummy
    export DATABASE_URL=sqlite://:memory:
    ${python.interpreter} -m django collectstatic --noinput
  '';
  meta.mainProgram = "zweili-search";
}
