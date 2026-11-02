#!/usr/bin/env bash
# Install (or update) the launchd job that runs scripts/daily.sh every day at HOUR (default 7).
# If the Mac is asleep then, launchd runs it on wake. Remove with:
#   launchctl bootout "gui/$(id -u)/com.hackerjobs.daily" && rm ~/Library/LaunchAgents/com.hackerjobs.daily.plist
set -euo pipefail

hour="${1:-7}"
repo_root="$(cd "$(dirname "$0")/.." && pwd)"
label="com.hackerjobs.daily"
plist="$HOME/Library/LaunchAgents/$label.plist"
log="$HOME/Library/Logs/hackerjobs.log"

mkdir -p "$(dirname "$plist")" "$(dirname "$log")"
cat > "$plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$label</string>
  <key>ProgramArguments</key>
  <array><string>$repo_root/scripts/daily.sh</string></array>
  <key>StartCalendarInterval</key>
  <dict><key>Hour</key><integer>$hour</integer><key>Minute</key><integer>0</integer></dict>
  <key>StandardOutPath</key><string>$log</string>
  <key>StandardErrorPath</key><string>$log</string>
</dict>
</plist>
PLIST

launchctl bootout "gui/$(id -u)/$label" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$plist"
echo "Installed $label: daily at $hour:00, logging to $log"
