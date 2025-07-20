#!/usr/bin/env bash

set -euo pipefail

PATH="$(nix build .#ci-tools --no-link --print-out-paths)/bin:$PATH"
result=$(nix build .#nginx-image --no-link --print-out-paths)
# ${variabe,,} converts a string to lowercase
echo "$REGISTRY_PASS" | skopeo login ghcr.io --username "$REGISTRY_USER" --password-stdin
skopeo copy --insecure-policy docker-archive://"$result" docker://"${REGISTRY,,}/zweili-search-nginx:latest"
