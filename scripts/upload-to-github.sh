#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET="$ROOT/upload_to_github.sh"

if [[ "${1:-}" == "--help" ]]; then
    cat <<'USAGE'
Usage: bash scripts/upload-to-github.sh

Guarded wrapper for the legacy upload_to_github.sh script.
This command may commit, change git remotes, and push to a remote repository.
It requires explicit interactive confirmation before delegation.
USAGE
    exit 0
fi

if [[ ! -f "$TARGET" ]]; then
    echo "upload_to_github.sh not found at repository root; upload wrapper cannot run." >&2
    exit 1
fi

printf '%s\n' "This upload path may run git add/commit/remote/push through upload_to_github.sh."
printf '%s' "Type 'upload' to continue: "
read -r CONFIRM
if [[ "$CONFIRM" != "upload" ]]; then
    echo "Cancelled."
    exit 0
fi

exec bash "$TARGET" "$@"
