BEGIN;

DROP VIEW IF EXISTS public.v_tank_pairs;

DO $$
DECLARE
  has_mother boolean;
  has_father boolean;
  has_alt_m  boolean;
  has_alt_f  boolean;
  col_mother text;
  col_father text;
  has_status  boolean;
  has_created boolean;
  has_cby     boolean;
  sqlview text;
BEGIN
  SELECT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='tank_pairs' AND column_name='mother_tank_id'
  ) INTO has_mother;

  SELECT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='tank_pairs' AND column_name='father_tank_id'
  ) INTO has_father;

  SELECT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='tank_pairs' AND column_name='tank_id_mother'
  ) INTO has_alt_m;

  SELECT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='tank_pairs' AND column_name='tank_id_father'
  ) INTO has_alt_f;

  IF has_mother AND has_father THEN
    col_mother := 'mother_tank_id';
    col_father := 'father_tank_id';
  ELSIF has_alt_m AND has_alt_f THEN
    col_mother := 'tank_id_mother';
    col_father := 'tank_id_father';
  ELSE
    RAISE EXCEPTION 'public.tank_pairs must have (mother_tank_id,father_tank_id) or (tank_id_mother,tank_id_father)';
  END IF;

  SELECT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='tank_pairs' AND column_name='status'
  ) INTO has_status;

  SELECT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='tank_pairs' AND column_name='created_at'
  ) INTO has_created;

  SELECT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='tank_pairs' AND column_name='created_by'
  ) INTO has_cby;

  sqlview := format($v$
    CREATE VIEW public.v_tank_pairs AS
    WITH tp AS (
      SELECT
        tp.tank_pair_code,
        tp.%1$I AS mother_tank_id,
        tp.%2$I AS father_tank_id,
        %3$s AS status,
        %4$s AS created_by,
        %5$s AS created_at
      FROM public.tank_pairs tp
    ),
    mom AS (
      SELECT
        t.tank_uuid AS tank_id,
        t.tank_code AS mom_tank_code,
        regexp_replace(t.tank_code, '^.*\(([^)]+)\).*$', '\1') AS mom_fish_code
      FROM public.v_tanks t
    ),
    dad AS (
      SELECT
        t.tank_uuid AS tank_id,
        t.tank_code AS dad_tank_code,
        regexp_replace(t.tank_code, '^.*\(([^)]+)\).*$', '\1') AS dad_fish_code
      FROM public.v_tanks t
    ),
    joined AS (
      SELECT
        tp.tank_pair_code,
        tp.mother_tank_id,
        tp.father_tank_id,
        m.mom_tank_code,
        d.dad_tank_code,
        m.mom_fish_code,
        d.dad_fish_code,
        tp.status,
        tp.created_by,
        tp.created_at
      FROM tp
      LEFT JOIN mom m ON m.tank_id = tp.mother_tank_id
      LEFT JOIN dad d ON d.tank_id = tp.father_tank_id
    )
    SELECT
      j.tank_pair_code,
      j.mother_tank_id,
      j.father_tank_id,
      j.mom_tank_code,
      j.dad_tank_code,
      j.mom_fish_code,
      j.dad_fish_code,
      COALESCE(fr_m.genotype_rollup,'') AS mom_genotype,
      COALESCE(fr_d.genotype_rollup,'') AS dad_genotype,
      j.status,
      j.created_by,
      j.created_at
    FROM joined j
    LEFT JOIN public.v_fish_rich fr_m ON fr_m.fish_code = j.mom_fish_code
    LEFT JOIN public.v_fish_rich fr_d ON fr_d.fish_code = j.dad_fish_code
    ORDER BY COALESCE(j.created_at, now()) DESC, j.tank_pair_code;
  $v$,
    col_mother,
    col_father,
    CASE WHEN has_status  THEN 'tp.status'     ELSE 'NULL::text' END,
    CASE WHEN has_cby     THEN 'tp.created_by' ELSE 'NULL::text' END,
    CASE WHEN has_created THEN 'tp.created_at' ELSE 'now()'      END
  );

  EXECUTE sqlview;
END $$;

COMMIT;
