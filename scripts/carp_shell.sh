# --- Staging ---
use_staging_pooler(){
  export DB_URL="postgresql://postgres.zebzrvjbalhazztvhhcm@aws-1-us-west-1.pooler.supabase.com:6543/postgres?sslmode=require"
}
use_staging_direct_ipv4(){
  ip=$(dig +short db.zebzrvjbalhazztvhhcm.supabase.co @1.1.1.1 | head -n1)
  export DB_URL="postgresql://postgres@db.zebzrvjbalhazztvhhcm.supabase.co:5432/postgres?sslmode=require&hostaddr=$ip"
}
use_staging_auto(){
  use_staging_pooler
  psql "$DB_URL" -Atc "select 1" >/dev/null 2>&1 || use_staging_direct_ipv4
}

# --- Prod ---
use_prod_pooler(){
  export DB_URL="postgresql://postgres.gzmbxhkckkspnefpxkgb@aws-0-us-east-2.pooler.supabase.com:6543/postgres?sslmode=require"
}
use_prod_direct_ipv4(){
  ip=$(dig +short db.gzmbxhkckkspnefpxkgb.supabase.co @1.1.1.1 | head -n1)
  export DB_URL="postgresql://postgres@db.gzmbxhkckkspnefpxkgb.supabase.co:5432/postgres?sslmode=require&hostaddr=$ip"
}
use_prod_auto(){
  use_prod_pooler
  psql "$DB_URL" -Atc "select 1" >/dev/null 2>&1 || use_prod_direct_ipv4
}

use_staging_direct_ipv4_pw() {
  ip=$(dig +short db.zebzrvjbalhazztvhhcm.supabase.co @1.1.1.1 | head -n1)
  export DB_URL="postgresql://postgres:carp_is_good_to_eat@db.zebzrvjbalhazztvhhcm.supabase.co:5432/postgres?sslmode=require&hostaddr=$ip"
}

run_app_staging() {
  pkill -f "streamlit run" || true
  use_staging_pooler
  psql "$DB_URL" -Atc "select 1" >/dev/null 2>&1 || use_staging_direct_ipv4_pw
  cd "$(git rev-parse --show-toplevel)"
  [ -f .venv/bin/activate ] && . .venv/bin/activate
  db_ok
  streamlit run "$(app_path)"
}

use_prod_direct_ipv4_pw() {
  ip=$(dig +short db.gzmbxhkckkspnefpxkgb.supabase.co @1.1.1.1 | head -n1)
  export DB_URL="postgresql://postgres:carp_is_good_to_eat@db.gzmbxhkckkspnefpxkgb.supabase.co:5432/postgres?sslmode=require&hostaddr=$ip"
}

run_app_prod() {
  pkill -f "streamlit run" || true
  use_prod_pooler
  psql "$DB_URL" -Atc "select 1" >/dev/null 2>&1 || use_prod_direct_ipv4_pw
  cd "$(git rev-parse --show-toplevel)"
  [ -f .venv/bin/activate ] && . .venv/bin/activate
  db_ok
  streamlit run "$(app_path)"
}

run_app_prod_pw() {
  pkill -f "streamlit run" || true
  use_prod_direct_ipv4_pw
  cd "$(git rev-parse --show-toplevel)"
  [ -f .venv/bin/activate ] && . .venv/bin/activate
  db_ok
  streamlit run "$(app_path)"
}