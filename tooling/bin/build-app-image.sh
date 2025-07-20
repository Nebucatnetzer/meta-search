#!/usr/bin/env bash
set -euo pipefail

PATH="$(nix build .#ci-tools --no-link --print-out-paths)/bin:$PATH"
result=$(nix build .#packages.aarch64-linux.app-image --no-link --print-out-paths)
# ${variabe,,} converts a string to lowercase
echo "$REGISTRY_PASS" | skopeo login ghcr.io --username "$REGISTRY_USER" --password-stdin
skopeo copy --all --insecure-policy docker-archive://"$result" "docker://${REGISTRY,,}/zweili-search-app:latest"

manifest-tool --username $REGISTRY_USER --password $REGISTRY_PASS push from-args --platforms linux/amd64,linux/arm64 --template "${REGISTRY,,}"/zweili-search-app:latest --target "${REGISTRY,,}"/zweili-search-app:latest
