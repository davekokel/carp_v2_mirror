#!/usr/bin/env bash
set -euo pipefail

: "${DB_URL:?Set DB_URL in your shell first (export DB_URL=...)}"

STAMP="$(date +%Y%m%d_%H%M%S)"
OUT_PNG="$HOME/Desktop/er_public_${STAMP}.png"
TMPDIR="$(mktemp -d)"
MMD="${TMPDIR}/er_public.mmd"

echo "• Building Mermaid ER at: ${MMD}"
printf "erDiagram\n" > "$MMD"

# Tables (public)
psql "$DB_URL" -Atc "
SELECT '  '||table_name||' {}'
FROM information_schema.tables
WHERE table_schema='public'
ORDER BY 1;" >> "$MMD"

# FKs (parent ||--o{ child : child_col)
psql "$DB_URL" -Atc "
SELECT '  '||ccu.table_name||' ||--o{ '||tc.table_name||' : '||kcu.column_name
FROM information_schema.table_constraints tc
JOIN information_schema.key_column_usage kcu
  ON tc.constraint_name=kcu.constraint_name AND tc.table_schema=kcu.table_schema
JOIN information_schema.constraint_column_usage ccu
  ON ccu.constraint_name=tc.constraint_name AND ccu.table_schema=tc.table_schema
WHERE tc.constraint_type='FOREIGN KEY' AND tc.table_schema='public'
ORDER BY 1;" >> "$MMD"

echo "• Rendering PNG to: ${OUT_PNG}"

# Try mermaid-cli via npx; fallback to Docker if needed
if command -v npx >/dev/null 2>&1; then
  npx -y @mermaid-js/mermaid-cli -i "$MMD" -o "$OUT_PNG" >/dev/null 2>&1 \
    || { echo "  npx render failed; trying Docker fallback..."; DOCKER_FALLBACK=1; }
else
  DOCKER_FALLBACK=1
fi

if [[ "${DOCKER_FALLBACK:-0}" == "1" ]]; then
  if command -v docker >/dev/null 2>&1; then
    docker run --rm -v "$TMPDIR":/data minlag/mermaid-cli \
      mmdc -i /data/er_public.mmd -o /data/er_public.png
    cp "${TMPDIR}/er_public.png" "$OUT_PNG"
  else
    echo "❌ Neither npx nor docker available. Install one of:"
    echo "   • npm:   npm i -g @mermaid-js/mermaid-cli"
    echo "   • docker: brew install --cask docker  (then run Docker Desktop)"
    exit 1
  fi
fi

echo "✅ Done: ${OUT_PNG}"