#!/usr/bin/env bash
# Daily update: fetch new posts, parse them with the configured models, export and deploy.
# Run by launchd (see scripts/install-daily.sh); logs go to ~/Library/Logs/hackerjobs.log.
set -euo pipefail

repo_root="$(cd "$(dirname "$0")/.." && pwd)"
# launchd starts with a minimal PATH.
export PATH="$HOME/.local/bin:$HOME/.bun/bin:$HOME/.lmstudio/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
cd "$repo_root"

echo "== $(date -u +%Y-%m-%dT%H:%M:%SZ) daily update"
lms server start
# Free the model's memory afterwards, whether or not the sync succeeds.
trap 'lms unload --all >/dev/null 2>&1 || true' EXIT
uv run hackerjobs sync
"$repo_root/scripts/deploy.sh"
echo "== done"
