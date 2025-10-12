#!/usr/bin/env bash
set -euo pipefail
echo "About to promote origin/main -> mirror/prod"
read -p "Type 'yes' to continue: " ans
[ "$ans" = "yes" ] || { echo "Aborted."; exit 1; }
git push mirror origin/main:prod
