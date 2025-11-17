rg -n "\bid_uuid\b" supabase carp_app -g '!**/__pycache__/**' -g '!supabase/migrations/_archive/**' && {
  echo "❌ id_uuid found above; replace with id"; exit 1; } || echo "✅ no id_uuid in live code"
