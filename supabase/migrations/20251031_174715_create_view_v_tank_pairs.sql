-- Create/replace public.v_tank_pairs using current schema shape.
DO $$
DECLARE
  mcol text;
  dcol text;
  vfish text;
  has_fp boolean;
  sql text;
BEGIN
  -- Detect mother/father tank columns on tank_pairs
  IF EXISTS (SELECT 1 FROM information_schema.columns
             WHERE table_schema='public' AND table_name='tank_pairs' AND column_name='mother_tank_id') THEN
    mcol := 'mother_tank_id'; dcol := 'father_tank_id';
  ELSIF EXISTS (SELECT 1 FROM information_schema.columns
                WHERE table_schema='public' AND table_name='tank_pairs' AND column_name='tank_id_mother') THEN
    mcol := 'tank_id_mother'; dcol := 'tank_id_father';
  ELSE
    RAISE EXCEPTION 'public.tank_pairs is missing mother/father tank id columns';
  END IF;

  -- Choose fish view
  IF EXISTS (SELECT 1 FROM information_schema.views
             WHERE table_schema='public' AND table_name='v_fish_rich') THEN
    vfish := 'public.v_fish_rich';
  ELSE
    vfish := 'public.v_fish';
  END IF;

  -- Does tank_pairs still have fish_pair_code?
  SELECT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='tank_pairs' AND column_name='fish_pair_code'
  ) INTO has_fp;

  -- Build view with dynamic mother/father columns and optional fish_pair_code
  sql := format($fmt$
    CREATE OR REPLACE VIEW public.v_tank_pairs AS
    WITH base AS (
      SELECT
        tp.tank_pair_code,
        %s AS fish_pair_code,
        tp.status,
        tp.created_by,
        tp.created_at,
        vtm.fish_code AS mom_fish_code,
        vtm.tank_code AS mom_tank_code,
        COALESCE(vfm.transgene_pretty_name, vfm.genotype_rollup, '') AS mom_genotype,
        vtf.fish_code AS dad_fish_code,
        vtf.tank_code AS dad_tank_code,
        COALESCE(vfd.transgene_pretty_name, vfd.genotype_rollup, '') AS dad_genotype
      FROM public.tank_pairs tp
      LEFT JOIN public.v_tanks vtm ON vtm.tank_%1$s = tp.%1$s
      LEFT JOIN public.v_tanks vtf ON vtf.tank_%2$s = tp.%2$s
      LEFT JOIN %3$s vfm ON vfm.fish_code = vtm.fish_code
      LEFT JOIN %3$s vfd ON vfd.fish_code = vtf.fish_code
    ),
    with_activity AS (
      SELECT
        b.*,
        (b.mom_fish_code || ' × ' || b.dad_fish_code) AS pair_fish,
        (b.mom_tank_code || ' × ' || b.dad_tank_code) AS pair_tanks,
        cx.cross_run_code AS latest_cross_code,
        cx.cross_date     AS latest_cross_date,
        cl.clutch_instance_code AS latest_clutch_code,
        cl.created_at     AS latest_clutch_created_at
      FROM base b
      LEFT JOIN LATERAL (
        SELECT ci.cross_run_code, ci.cross_date, ci.created_at
        FROM public.cross_instances ci
        WHERE ci.tank_pair_code = b.tank_pair_code
        ORDER BY ci.created_at DESC NULLS LAST, ci.cross_date DESC NULLS LAST
        LIMIT 1
      ) AS cx ON TRUE
      LEFT JOIN LATERAL (
        SELECT cl.clutch_instance_code, cl.created_at
        FROM public.clutch_instances cl
        WHERE cl.tank_pair_code = b.tank_pair_code
        ORDER BY cl.created_at DESC NULLS LAST
        LIMIT 1
      ) AS cl ON TRUE
    )
    SELECT * FROM with_activity;
  $fmt$,
    CASE WHEN has_fp THEN 'tp.fish_pair_code' ELSE 'NULL::text' END,
    mcol, dcol, vfish
  );

  EXECUTE sql;
END
$$;

COMMENT ON VIEW public.v_tank_pairs IS
  'Overview of tank pairings with current mother/father fish & tanks, genotypes, and latest cross/clutch activity.';
