BEGIN;

DROP VIEW IF EXISTS public.v_fish_tank_history;

DO $$
DECLARE
  fish_col text;
  tank_col text;
BEGIN
  SELECT CASE
           WHEN EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='join_fish_tanks' AND column_name='fish_uuid') THEN 'fish_uuid'
           WHEN EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='join_fish_tanks' AND column_name='fish_id') THEN 'fish_id'
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
      jft.id::text        AS join_id,
      jft.%I::text        AS fish_id,
      jft.%I::text        AS tank_id,
      jft.valid_from,
      jft.valid_to,
      (jft.valid_to IS NULL) AS is_current
    FROM public.join_fish_tanks jft
  $f$, fish_col, tank_col);
END$$;

COMMIT;
