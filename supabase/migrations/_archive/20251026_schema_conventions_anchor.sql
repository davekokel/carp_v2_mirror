BEGIN;

CREATE TABLE IF NOT EXISTS public._schema_version (
  key text PRIMARY KEY,
  version text NOT NULL,
  details jsonb DEFAULT '{}'::jsonb,
  applied_at timestamptz NOT NULL DEFAULT now()
);

INSERT INTO public._schema_version (key, version, details)
VALUES (
  'conventions_uuid_pk',
  'v2025-10-26',
  jsonb_build_object(
    'summary','CARP UUID conventions: <entity>_uuid PKs, FKs named after PKs, link tables with started_at/ended_at, created_at/updated_at + trigger, v_ view prefix',
    'entities', jsonb_build_array('fish','tanks','fish_tank_memberships')
  )
)
ON CONFLICT (key) DO UPDATE
SET version = EXCLUDED.version,
    details = EXCLUDED.details,
    applied_at = now();

CREATE OR REPLACE VIEW public.v_conventions_checks AS
WITH
pk_fish AS (
  SELECT EXISTS (
    SELECT 1
    FROM information_schema.table_constraints tc
    JOIN information_schema.key_column_usage k
      ON tc.constraint_name=k.constraint_name
     AND tc.table_schema=k.table_schema
     AND tc.table_name=k.table_name
    WHERE tc.table_schema='public'
      AND tc.table_name='fish'
      AND tc.constraint_type='PRIMARY KEY'
      AND k.column_name='fish_uuid'
  ) AS ok
),
pk_tanks AS (
  SELECT EXISTS (
    SELECT 1
    FROM information_schema.table_constraints tc
    JOIN information_schema.key_column_usage k
      ON tc.constraint_name=k.constraint_name
     AND tc.table_schema=k.table_schema
     AND tc.table_name=k.table_name
    WHERE tc.table_schema='public'
      AND tc.table_name='tanks'
      AND tc.constraint_type='PRIMARY KEY'
      AND k.column_name='tank_uuid'
  ) AS ok
),
ftm_cols AS (
  SELECT
    EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='fish_tank_memberships') AND
    EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='fish_tank_memberships' AND column_name='fish_uuid') AND
    EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='fish_tank_memberships' AND column_name='tank_uuid') AND
    EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='fish_tank_memberships' AND column_name='started_at') AND
    EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='fish_tank_memberships' AND column_name='ended_at') AS ok
),
idx_active AS (
  SELECT EXISTS (
    SELECT 1
    FROM pg_class c
    JOIN pg_index i ON i.indexrelid=c.oid
    JOIN pg_class t ON t.oid=i.indrelid
    WHERE c.relname='uq_tank_active'
      AND t.relname='fish_tank_memberships'
      AND pg_get_expr(i.indpred, i.indrelid) ILIKE '%ended_at IS NULL%'
  ) AS ok
),
trg_updated AS (
  SELECT EXISTS (
    SELECT 1 FROM pg_trigger WHERE tgname='trg_fish_tank_memberships_updated_at'
  ) AS ok
)
SELECT * FROM (
  SELECT 'fish_pk_is_fish_uuid' AS check_name, (SELECT ok FROM pk_fish) AS ok, 'PK(fish.fish_uuid)' AS details
  UNION ALL
  SELECT 'tanks_pk_is_tank_uuid', (SELECT ok FROM pk_tanks), 'PK(tanks.tank_uuid)'
  UNION ALL
  SELECT 'ftm_required_columns', (SELECT ok FROM ftm_cols), 'fish_uuid,tank_uuid,started_at,ended_at'
  UNION ALL
  SELECT 'ftm_one_active_fish_per_tank', (SELECT ok FROM idx_active), 'uq_tank_active with predicate ended_at IS NULL'
  UNION ALL
  SELECT 'ftm_updated_at_trigger', (SELECT ok FROM trg_updated), 'trigger trg_fish_tank_memberships_updated_at'
) s;

COMMIT;
