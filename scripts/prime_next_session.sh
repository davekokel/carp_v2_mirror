#!/usr/bin/env bash
set -euo pipefail
REPO="${1:-$HOME/Documents/github/carp_v2}"
ENV_LABEL="${ENV_LABEL:-staging}"
FEATURE_BRANCH="${FEATURE_BRANCH:-}"
TS="$(date +%Y%m%d_%H%M%S)"
OUTDIR="$REPO/priming/${ENV_LABEL}_next_session_${TS}"
mkdir -p "$OUTDIR"
cd "$REPO"
if [ -z "${FEATURE_BRANCH}" ]; then
  if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    FEATURE_BRANCH="$(git rev-parse --abbrev-ref HEAD)"
  else
    FEATURE_BRANCH="unknown"
  fi
fi
printf "%s\n" "$FEATURE_BRANCH" > "$OUTDIR/feature_branch.txt"
{ echo "# repo tree (depth 3)"; date; } > "$OUTDIR/repo_tree.txt"
find . -path ./.git -prune -o -maxdepth 3 -print | sed 's|^\./||' >> "$OUTDIR/repo_tree.txt"
{
  echo "# git summary"; date
  echo "branch: $(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo 'n/a')"
  git status -sb || true
  git remote -v || true
  git log --oneline -n 25 || true
} > "$OUTDIR/git_summary.txt"
if [ -x "$REPO/scripts/prime_schema_staging.sh" ]; then
  "$REPO/scripts/prime_schema_staging.sh"
  SCHEMA_ZIP="$(ls -t "$REPO/priming"/priming_${ENV_LABEL}_schema_*.zip 2>/dev/null | head -1 || true)"
  if [ -n "${SCHEMA_ZIP:-}" ]; then cp "$SCHEMA_ZIP" "$OUTDIR/"; fi
fi
printf "Environment: %s\nFeature branch: %s\nGenerated: %s\n" "$ENV_LABEL" "$FEATURE_BRANCH" "$TS" > "$OUTDIR/README.txt"
cd "$REPO/priming"
zip -r "priming_${ENV_LABEL}_next_session_${TS}.zip" "$(basename "$OUTDIR")"
echo "Created: $REPO/priming/priming_${ENV_LABEL}_next_session_${TS}.zip"