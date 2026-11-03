#!/usr/bin/env bash
# Back up the database as a consistent, checked, gzipped SQLite snapshot, keeping the last
# HACKERJOBS_BACKUP_KEEP days (default 14). The database holds decoded email addresses, so backups
# belong in private storage only; the default is iCloud Drive.
set -euo pipefail

repo_root="$(cd "$(dirname "$0")/.." && pwd)"
backup_dir="${HACKERJOBS_BACKUP_DIR:-$HOME/Library/Mobile Documents/com~apple~CloudDocs/Backups/hackerjobs}"
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

# macOS lets launchd jobs write to iCloud Drive but not list it, so expired backups are removed by
# name: those from $keep days ago back to a year before that.
expired=()
for ((age = keep; age < keep + 366; age++)); do
  expired+=("$backup_dir/hackerjobs-$(date -v-"${age}"d +%Y-%m-%d).db.gz")
done
rm -f -- "${expired[@]}"
echo "Backed up to $target ($(du -h "$target" | cut -f1))"
