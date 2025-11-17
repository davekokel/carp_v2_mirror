#!/usr/bin/env bash
set -euo pipefail
REPO="${1:-$HOME/Documents/github/carp_v2}"
osascript <<OSA
tell application "Terminal"
  do script "cd \"${REPO}\" && source .venv/bin/activate && use_staging && loadenv"
  activate
end tell
OSA
