# scripts/use_db.sh
# Usage: source scripts/use_db.sh

use_local() {
  export DB_URL='postgresql://postgres@127.0.0.1:54322/postgres?sslmode=disable'
  echo "DB_URL=$DB_URL"
}

# STAGING (pooler 6543) – user includes project ref
use_staging() {
  export DB_URL='postgresql://postgres.zebzrvjbalhazztvhhcm@aws-1-us-west-1.pooler.supabase.com:6543/postgres?sslmode=require'
  echo "DB_URL=$DB_URL"
}

# STAGING (direct 5432) – user is plain 'postgres'
use_staging_direct() {
  export DB_URL='postgresql://postgres@db.zebzrvjbalhazztvhhcm.supabase.co:5432/postgres?sslmode=require'
  echo "DB_URL=$DB_URL"
}

# PROD (pooler 6543)
use_prod() {
  export DB_URL='postgresql://postgres.gzmbxhkckkspnefpxkgb@aws-0-us-east-2.pooler.supabase.com:6543/postgres?sslmode=require'
  echo "DB_URL=$DB_URL"
}

# PROD (direct 5432)
use_prod_direct() {
  export DB_URL='postgresql://postgres@db.gzmbxhkckkspnefpxkgb.supabase.co:5432/postgres?sslmode=require'
  echo "DB_URL=$DB_URL"
}