#!/usr/bin/env bash
set -euo pipefail

search_scopes=(
  "supabase/ui/pages"
  "supabase/ui/streamlit_app.py"
  "supabase/ui/auth_gate.py"
  "supabase/ui/lib_shared.py"
)

echo -e "status\thits\tpath\texample"

scan_file() {
  local f="$1"; local stem="${f##*/}"; stem="${stem%.py}"
  local mod_comp="supabase.ui.components.${stem}"
  local mod_lib="supabase.ui.lib.${stem}"

  # search only in UI pages + a few entry files, exclude the file itself
  local hits
  hits=$(rg -n --hidden --glob '!**/.git/**' \
    -g "!${f}" \
    -e "from ${mod_comp} import " \
    -e "import ${mod_comp}" \
    -e "from ${mod_lib} import " \
    -e "import ${mod_lib}" \
    -- ${search_scopes[@]} | wc -l | tr -d ' ')

  local example
  example=$(rg -n --hidden --glob '!**/.git/**' \
    -g "!${f}" \
    -e "from ${mod_comp} import " \
    -e "import ${mod_comp}" \
    -e "from ${mod_lib} import " \
    -e "import ${mod_lib}" \
    -- ${search_scopes[@]} | head -n 1 || true)

  if [ "${hits}" -gt 0 ]; then
    echo -e "USED\t${hits}\t${f}\t${example}"
  else
    echo -e "UNREFERENCED?\t0\t${f}\t"
  fi
}

for f in supabase/ui/components/*.py supabase/ui/lib/*.py; do
  [ -f "$f" ] || continue
  # ignore dunder files
  case "$f" in *"/__init__.py") continue;; esac
  scan_file "$f"
done
