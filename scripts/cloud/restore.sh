#!/usr/bin/env bash
# One recovery method for both pinned PETSc environments. No solver or latest URLs.
set -euo pipefail
root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
version=${1:-3.23.7}
state=${2:-"$root/.cloud"}
case "$version" in 3.23.7|3.19.6) ;; *) echo 'Expected PETSc 3.23.7 or 3.19.6' >&2; exit 2;; esac
[[ $(uname -s) == Linux && $(uname -m) == x86_64 ]] || { echo 'Requires Linux x86_64' >&2; exit 2; }
mkdir -p "$state"
state=$(cd "$state" && pwd)
lock="$root/environments/petsc-$version-linux-64.lock"
sha=701f39c06f8e6a670a0e186c8479b9e5c0502a2f0cda6cef65d83bdd2875e8bd
mamba="$state/micromamba"
if [[ ! -f "$mamba" ]]; then
    curl --fail --location --retry 3 https://github.com/mamba-org/micromamba-releases/releases/download/2.10.0-0/micromamba-linux-64 -o "$mamba"
fi
printf '%s  %s\n' "$sha" "$mamba" | sha256sum --check
chmod +x "$mamba"
export MAMBA_ROOT_PREFIX="$state/mamba"
# Explicit packages include hashes. Re-running verifies the lock, then uses the cache.
prefix="$state/petsc-$version"
action=create
[[ ! -f "$prefix/conda-meta/history" ]] || action=install
"$mamba" "$action" --yes --prefix "$prefix" --file "$lock"
printf '%s\n' "$prefix" > "$state/prefix-$version.txt"
