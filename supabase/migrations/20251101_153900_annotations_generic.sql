BEGIN;

-- legacy placeholder (replaces earlier broken trigger migration)
-- keep required extensions; actual tables/views/triggers are created by 20251101_154800_* and later files

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS pgcrypto;

COMMIT;
