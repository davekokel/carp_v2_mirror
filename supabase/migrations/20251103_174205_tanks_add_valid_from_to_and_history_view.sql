BEGIN;

CREATE EXTENSION IF NOT EXISTS btree_gist;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='join_fish_tanks' AND column_name='valid_from')
  THEN EXECUTE 'ALTER TABLE public.join_fish_tanks ADD COLUMN valid_from timestamptz'; END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='join_fish_tanks' AND column_name='valid_to')
  THEN EXECUTE 'ALTER TABLE public.join_fish_tanks ADD COLUMN valid_to timestamptz'; END IF;
END$$;

DO $$
DECLARE
  src_from text;
  src_to   text;
BEGIN
  SELECT col INTO src_from FROM (
    SELECT 'since'::text AS col WHERE EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='join_fish_tanks' AND column_name='since')
    UNION ALL SELECT 'created_at'::text AS col WHERE EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='join_fish_tanks' AND column_name='created_at')
  ) s LIMIT 1;

  SELECT col INTO src_to FROM (
    SELECT 'until'::text AS col WHERE EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='join_fish_tanks' AND column_name='until')
  ) s LIMIT 1;

  IF src_from IS NULL THEN
    EXECUTE 'UPDATE public.join_fish_tanks SET valid_from = COALESCE(valid_from, now()) WHERE valid_from IS NULL';
  ELSE
    EXECUTE format('UPDATE public.join_fish_tanks SET valid_from = COALESCE(valid_from, %I, now()) WHERE valid_from IS NULL', src_from);
  END IF;

  IF src_to IS NOT NULL THEN
    EXECUTE format('UPDATE public.join_fish_tanks SET valid_to = COALESCE(valid_to, %I) WHERE valid_to IS NULL', src_to);
  END IF;
END$$;

DO $$
BEGIN
  ALTER TABLE public.join_fish_tanks ALTER COLUMN valid_from SET NOT NULL;
EXCEPTION WHEN others THEN NULL;
END$$;

DROP VIEW IF EXISTS public.v_fish_tank_history;

DO $$
DECLARE
  fish_col text;
  tank_col text;
BEGIN
  SELECT CASE
           WHEN EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='join_fish_tanks' AND column_name='fish_id') THEN 'fish_id'
           WHEN EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='join_fish_tanks' AND column_name='fish_uuid') THEN 'fish_uuid'
           ELSE NULL
         END INTO fish_col;

  SELECT CASE
           WHEN EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='join_fish_tanks' AND column_name='tank_id') THEN 'tank_id'
           WHEN EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='join_fish_tanks' AND column_name='tank_uuid') THEN 'tank_uuid'
           ELSE NULL
         END INTO tank_col;

  IF fish_col IS NULL OR tank_col IS NULL THEN
    RAISE EXCEPTION 'join_fish_tanks must have fish_* and tank_* columns';
  END IF;

  EXECUTE format($f$
    CREATE VIEW public.v_fish_tank_history AS
    SELECT
      jft.id::text  AS join_id,
      jft.%I::text  AS fish_id,
      jft.%I::text  AS tank_id,
      jft.valid_from,
      jft.valid_to,
      (jft.valid_to IS NULL) AS is_current
    FROM public.join_fish_tanks jft
  $f$, fish_col, tank_col);
END$$;

COMMIT;
