#!/usr/bin/env bash
# Build the site and publish it to GitHub Pages as the only commit on the gh-pages branch.
# The data changes daily, so keeping no history keeps the repository small.
set -euo pipefail

repo_root="$(cd "$(dirname "$0")/.." && pwd)"
remote_url="$(git -C "$repo_root" remote get-url origin)"
site="$(mktemp -d)"
trap 'rm -rf "$site"' EXIT

(cd "$repo_root/web" && bun run build)
cp -R "$repo_root/web/dist/." "$site"
touch "$site/.nojekyll"  # serve files as built, without Jekyll processing

git -C "$site" init --quiet --initial-branch gh-pages
git -C "$site" add --all
git -C "$site" commit --quiet --message "Deploy $(date -u +%Y-%m-%dT%H:%MZ)"
git -C "$site" push --quiet --force "$remote_url" gh-pages
echo "Deployed to gh-pages"
