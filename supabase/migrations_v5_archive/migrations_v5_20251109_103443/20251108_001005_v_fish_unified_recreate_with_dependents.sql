BEGIN;

-- 1) Drop dependents first
DROP VIEW IF EXISTS public.v_tank_pairs;
DROP VIEW IF EXISTS public.v_fish_main;
DROP VIEW IF EXISTS public.v_fish_unified;

-- 2) Recreate v_fish_unified (minimal, portable)
CREATE VIEW public.v_fish_unified AS
WITH markers AS (
  SELECT
    f.fish_code,
    (ta.transgene_base_code || '(' || ta.allele_name || ')')::text AS marker_label
  FROM public.join_fish_transgene_alleles jf
  JOIN public.transgene_alleles ta
    ON ta.transgene_base_code = jf.transgene_base_code
   AND ta.allele_number       = jf.allele_number
  JOIN public.fish f
    ON f.id = jf.fish_id
  WHERE NULLIF(ta.allele_name,'') IS NOT NULL
),
gp AS (
  SELECT
    m.fish_code,
    string_agg(DISTINCT m.marker_label, ', ' ORDER BY m.marker_label) AS genotype_pretty
  FROM markers m
  GROUP BY m.fish_code
)
SELECT
  f.fish_code,
  COALESCE(gp.genotype_pretty,'') AS genotype_pretty
FROM public.fish f
LEFT JOIN gp ON gp.fish_code = f.fish_code;

-- 3) Shim v_fish_main
CREATE VIEW public.v_fish_main AS
SELECT * FROM public.v_fish_unified;

-- 4) Recreate v_tank_pairs schema-aware (no hard refs to tp.status/created_by/created_at)
DO $$
DECLARE
  has_mf   boolean;  -- mother_tank_id / father_tank_id
  has_alt  boolean;  -- tank_id_mother / tank_id_father
  has_stat boolean;
  has_by   boolean;
  has_at   boolean;

  mom_col  text;
  dad_col  text;

  sel_status     text;
  sel_created_by text;
  sel_created_at text;

  sql_text text;
BEGIN
  -- which mother/father cols exist?
  SELECT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='tank_pairs' AND column_name='mother_tank_id'
  ) INTO has_mf;

  SELECT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='tank_pairs' AND column_name='tank_id_mother'
  ) INTO has_alt;

  IF NOT has_mf AND NOT has_alt THEN
    RAISE EXCEPTION 'tank_pairs must have mother_tank_id/father_tank_id or tank_id_mother/tank_id_father';
  END IF;

  mom_col := CASE WHEN has_mf THEN 'tp.mother_tank_id' ELSE 'tp.tank_id_mother' END;
  dad_col := CASE WHEN has_mf THEN 'tp.father_tank_id' ELSE 'tp.tank_id_father' END;

  -- optional tp columns
  SELECT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='tank_pairs' AND column_name='status'
  ) INTO has_stat;

  SELECT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='tank_pairs' AND column_name='created_by'
  ) INTO has_by;

  SELECT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='tank_pairs' AND column_name='created_at'
  ) INTO has_at;

  sel_status     := CASE WHEN has_stat THEN ', COALESCE(tp.status, '''') AS status'
                         ELSE ', NULL::text AS status' END;
  sel_created_by := CASE WHEN has_by   THEN ', tp.created_by'
                         ELSE ', NULL::text AS created_by' END;
  sel_created_at := CASE WHEN has_at   THEN ', tp.created_at'
                         ELSE ', NULL::timestamptz AS created_at' END;

  sql_text := '
    CREATE VIEW public.v_tank_pairs AS
    SELECT
      tp.tank_pair_code,
      vtm.fish_code                                   AS mom_fish_code,
      vtm.tank_code                                   AS mom_tank_code,
      COALESCE(vfm.genotype_pretty, '''')             AS mom_genotype,
      vtf.fish_code                                   AS dad_fish_code,
      vtf.tank_code                                   AS dad_tank_code,
      COALESCE(vff.genotype_pretty, '''')             AS dad_genotype' ||
      sel_status || sel_created_by || sel_created_at || '
    FROM public.tank_pairs tp
    LEFT JOIN public.v_tanks vtm ON vtm.tank_uuid = ' || mom_col || '
    LEFT JOIN public.v_tanks vtf ON vtf.tank_uuid = ' || dad_col || '
    LEFT JOIN public.v_fish_unified vfm ON vfm.fish_code = vtm.fish_code
    LEFT JOIN public.v_fish_unified vff ON vff.fish_code = vtf.fish_code';

  EXECUTE sql_text;
END $$;

COMMIT;
