-- Create/replace public.v_tank_pairs from current schema objects
DO $$
DECLARE
  use_mother text := NULL;
  use_father text := NULL;
  fish_view  text := NULL;
  fish_gene  text := NULL; -- the pretty genotype column to use or NULL
  have_fp    boolean := FALSE;
  dyn_sql    text;
BEGIN
  -- which tank_pairs columns exist?
  IF EXISTS (SELECT 1 FROM information_schema.columns
             WHERE table_schema='public' AND table_name='tank_pairs' AND column_name='mother_tank_id')
     AND EXISTS (SELECT 1 FROM information_schema.columns
                 WHERE table_schema='public' AND table_name='tank_pairs' AND column_name='father_tank_id')
  THEN
     use_mother := 'mother_tank_id';
     use_father := 'father_tank_id';
  ELSIF EXISTS (SELECT 1 FROM information_schema.columns
                WHERE table_schema='public' AND table_name='tank_pairs' AND column_name='tank_id_mother')
     AND EXISTS (SELECT 1 FROM information_schema.columns
                 WHERE table_schema='public' AND table_name='tank_pairs' AND column_name='tank_id_father')
  THEN
     use_mother := 'tank_id_mother';
     use_father := 'tank_id_father';
  ELSE
     RAISE EXCEPTION 'public.tank_pairs missing mother/father tank id columns (expected mother_tank_id/father_tank_id or tank_id_mother/tank_id_father)';
  END IF;

  -- choose fish view
  IF EXISTS (SELECT 1 FROM information_schema.views WHERE table_schema='public' AND table_name='v_fish_rich') THEN
    fish_view := 'public.v_fish_rich';
  ELSIF EXISTS (SELECT 1 FROM information_schema.views WHERE table_schema='public' AND table_name='v_fish') THEN
    fish_view := 'public.v_fish';
  ELSE
    -- still allow view without genotype; set to NULLs
    fish_view := NULL;
  END IF;

  -- pick a genotype column if present on chosen fish view
  IF fish_view IS NOT NULL THEN
    IF EXISTS (SELECT 1 FROM information_schema.columns
               WHERE table_schema='public'
                 AND table_name = split_part(fish_view, '.', 2)
                 AND column_name = 'transgene_pretty_name') THEN
      fish_gene := 'transgene_pretty_name';
    ELSIF EXISTS (SELECT 1 FROM information_schema.columns
               WHERE table_schema='public'
                 AND table_name = split_part(fish_view, '.', 2)
                 AND column_name = 'genotype_roLlup') THEN  -- typo guard; fixed below
      fish_gene := 'genotype_rollup';
    ELSIF EXISTS (SELECT 1 FROM information_schema.columns
               WHERE table_schema='public'
                 AND table_name = split_part(fish_view, '.', 2)
                 AND column_name = 'genotype_rollup') THEN
      fish_gene := 'genotype_rollup';
    END IF;
  END IF;

  -- whether tank_pairs still has fish_pair_code
  SELECT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='tank_pairs' AND column_name='fish_pair_code'
  ) INTO have_fp;

  -- drop old view if present
  IF EXISTS (SELECT 1 FROM information_schema.views WHERE table_schema='public' AND table_name='v_tank_pairs') THEN
    EXECUTE 'DROP VIEW public.v_tank_pairs';
  END IF;

  -- assemble dynamic SQL
  dyn_sql := 'CREATE VIEW public.v_tank_pairs AS
    WITH base AS (
      SELECT
        tp.tank_pair_code,
        ' || CASE WHEN have_fp THEN 'tp.fish_pair_code' ELSE 'NULL::text AS fish_pair_code' END || ',
        tp.status,
        tp.created_by,
        tp.created_at,
        vtm.fish_code AS mom_fish_code,
        vtm.tank_code AS mom_tank_code,
        ' ||
        CASE
          WHEN fish_view IS NULL OR fish_gene IS NULL
            THEN 'NULL::text AS mom_genotype'
          ELSE format('COALESCE(vfm.%1$s, '''') AS mom_genotype', fish_gene)
        END || ',
        vtf.fish_code AS dad_fish_code,
        vtf.tank_code AS dad_tank_code,
        ' ||
        CASE
          WHEN fish_view IS NULL OR fish_gene IS NULL
            THEN 'NULL::text AS dad_genotype'
          ELSE format('COALESCE(vfd.%1$s, '''') AS dad_genotype', fish_gene)
        END || '
      FROM public.tank_pairs tp
      LEFT JOIN public.v_tanks vtm ON vtm.tank_uuid = tp.' || use_mother || '
      LEFT JOIN public.v_tanks vtf ON vtf.tank_uuid = tp.' || use_father || '
      ' || COALESCE('LEFT JOIN ' || fish_view || ' vfm ON vfm.fish_code = vtm.fish_code', '') || '
      ' || COALESCE('LEFT JOIN ' || fish_view || ' vfd ON vfd.fish_code = vtf.fish_code', '') || '
    ),
    act AS (
      SELECT b.*,
             (COALESCE(b.mom_fish_code, '''') || '' × '' || COALESCE(b.dad_fish_code, '''')) AS pair_fish,
             (COALESCE(b.mom_tank_code, '''') || '' × '' || COALESCE(b.dad_tank_code, '''')) AS pair_tanks,
             cx.cross_run_code AS latest_cross_code,
             cx.cross_date     AS latest_cross_date,
             cl.clutch_instance_code AS latest_clutch_code,
             cl.created_at     AS latest_clutch_created_at
      FROM base b
      LEFT JOIN LATERAL (
        SELECT ci.cross_run_code, ci.cross_date, ci.created_at
        FROM public.cross_items ci -- placeholder, replaced below
        ORDER BY ci.created_at DESC NULLS LAST, ci.cross_date DESC NULLS LAST
        LIMIT 1
      ) cx ON TRUE
      LEFT JOIN LATERAL (
        SELECT cl.clutch_instance_code, cl.created_at
        FROM public.clutch_instances cl
        JOIN public.cross_instances ci ON ci.id = cl.cross_instance_id
        WHERE ci.tank_pair_code = b.tank_pair_code
        ORDER BY cl.created_at DESC NULLS LAST
        LIMIT 1
      ) cl ON TRUE
    )
    SELECT * FROM act';

  -- fix the placeholder table names for lateral joins (quoting inside string literal is awkward)
  dyn_sql := replace(dyn_sql, 'public.cross_items', 'public.cross_instances');

  -- create the view
  EXECUTE dyn_sql;

  -- comment
  EXECUTE $c$
    COMMENT ON VIEW public.v_tank_pairs IS
    'Overview of tank pairings with mother/father fish+tanks, optional genotype (from v_fish_*), and latest cross/clutch activity.'
  $c$;
END
$$;
