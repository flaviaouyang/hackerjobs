#!/usr/bin/env bash
# Back up the database as a consistent, checked, gzipped SQLite snapshot, keeping the newest
# HACKERJOBS_BACKUP_KEEP (default 14). The database holds decoded email addresses, so backups
# belong in private storage only. The default is a local folder because macOS stops launchd jobs
# from listing iCloud Drive or touching files an earlier run left there.
set -euo pipefail

repo_root="$(cd "$(dirname "$0")/.." && pwd)"
backup_dir="${HACKERJOBS_BACKUP_DIR:-$HOME/Backups/hackerjobs}"
keep="${HACKERJOBS_BACKUP_KEEP:-14}"
snapshot="$(mktemp -d)"
trap 'rm -rf "$snapshot"' EXIT

# .backup copies a consistent state even while the database is in use; a file copy may not.
sqlite3 "$repo_root/data/hackerjobs.db" ".backup '$snapshot/hackerjobs.db'"
check="$(sqlite3 "$snapshot/hackerjobs.db" "PRAGMA integrity_check")"
if [ "$check" != "ok" ]; then
  echo "Backup failed its integrity check: $check" >&2
  exit 1
fi

mkdir -p "$backup_dir"
target="$backup_dir/hackerjobs-$(date +%Y-%m-%d).db.gz"
gzip -c "$snapshot/hackerjobs.db" > "$target.partial"
mv "$target.partial" "$target"

# Names sort by date, so everything after the newest $keep is old.
find "$backup_dir" -maxdepth 1 -name 'hackerjobs-*.db.gz' | sort -r | tail -n "+$((keep + 1))" |
  while IFS= read -r old; do rm -- "$old"; done
echo "Backed up to $target ($(du -h "$target" | cut -f1))"
