BEGIN;

-- Recreate v_tank_pairs with schema-aware joins and optional tp.* columns.
DROP VIEW IF EXISTS public.v_tank_pairs;

DO $$
DECLARE
  has_mf         boolean;  -- mother_tank_id / father_tank_id
  has_alt        boolean;  -- tank_id_mother / tank_id_father
  has_status     boolean;
  has_created_by boolean;
  has_created_at boolean;

  sel_status     text;
  sel_created_by text;
  sel_created_at text;

  mom_col        text;
  dad_col        text;

  sql_text       text;
BEGIN
  -- Which mother/father columns exist on tank_pairs?
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

  -- Optional columns on tank_pairs
  SELECT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='tank_pairs' AND column_name='status'
  ) INTO has_status;

  SELECT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='tank_pairs' AND column_name='created_by'
  ) INTO has_created_by;

  SELECT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='tank_pairs' AND column_name='created_at'
  ) INTO has_created_at;

  sel_status     := CASE WHEN has_status     THEN ', COALESCE(tp.status, '''') AS status'
                         ELSE ', NULL::text AS status' END;
  sel_created_by := CASE WHEN has_created_by THEN ', tp.created_by'
                         ELSE ', NULL::text AS created_by' END;
  sel_created_at := CASE WHEN has_created_at THEN ', tp.created_at'
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
