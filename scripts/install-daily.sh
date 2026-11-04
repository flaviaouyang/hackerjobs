#!/usr/bin/env bash
# Install (or update) the launchd job that runs scripts/daily.sh while the month's threads are
# active. Threads open around 11:00 Eastern on the first weekday and take most of their posts in
# the first days, so the job runs three times a day on the 1st-4th and at 9:00 on the 5th-10th.
# Threads close to new comments after about 14 days; a run on the 16th picks up the stragglers.
# If the Mac is asleep at a run time, launchd runs it on wake. Remove with:
#   launchctl bootout "gui/$(id -u)/com.hackerjobs.daily" && rm ~/Library/LaunchAgents/com.hackerjobs.daily.plist
set -euo pipefail

repo_root="$(cd "$(dirname "$0")/.." && pwd)"
label="com.hackerjobs.daily"
plist="$HOME/Library/LaunchAgents/$label.plist"
log="$HOME/Library/Logs/hackerjobs.log"

mkdir -p "$(dirname "$plist")" "$(dirname "$log")"
runs=""
add_run() { runs+="    <dict><key>Day</key><integer>$1</integer><key>Hour</key><integer>$2</integer><key>Minute</key><integer>0</integer></dict>
"; }
for day in 1 2 3 4; do for hour in 12 17 22; do add_run "$day" "$hour"; done; done
for day in 5 6 7 8 9 10 16; do add_run "$day" 9; done

cat > "$plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$label</string>
  <key>ProgramArguments</key>
  <array><string>$repo_root/scripts/daily.sh</string></array>
  <key>StartCalendarInterval</key>
  <array>
$runs  </array>
  <key>StandardOutPath</key><string>$log</string>
  <key>StandardErrorPath</key><string>$log</string>
</dict>
</plist>
PLIST

launchctl bootout "gui/$(id -u)/$label" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$plist"
echo "Installed $label: 1st-4th at 12:00, 17:00 and 22:00; 5th-10th and 16th at 9:00; logging to $log"
