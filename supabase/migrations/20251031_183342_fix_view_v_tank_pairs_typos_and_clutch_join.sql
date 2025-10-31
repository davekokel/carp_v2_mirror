DO $$
DECLARE
  mcol text;
  dcol text;
  fish_view text;
  gene_col text;
  has_fp boolean;
  dyn_sql text;
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='tank_pairs' AND column_name='mother_tank_id')
     AND EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='tank_pairs' AND column_name='father_tank_id')
  THEN mcol:='mother_tank_id'; dcol:='father_tank_id';
  ELSIF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='tank_pairs' AND column_name='tank_id_mother')
     AND EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='tank_pairs' AND column_name='tank_id_father')
  THEN mcol:='tank_id_mother'; dcol:='tank_id_father';
  ELSE RAISE EXCEPTION 'public.tank_pairs missing mother/father tank id columns'; END IF;

  IF EXISTS (SELECT 1 FROM information_schema.views WHERE table_schema='public' AND table_name='v_fish_rich') THEN
    fish_view:='public.v_fish_rich';
  ELSIF EXISTS (SELECT 1 FROM information_schema.views WHERE table_schema='public' AND table_name='v_fish') THEN
    fish_view:='public.v_fish';
  ELSE fish_view:=NULL; END IF;

  IF fish_view IS NOT NULL AND EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name=split_part(fish_view,'.',2) AND column_name='transgene_pretty_name')
  THEN gene_col:='transgene_pretty_name';
  ELSIF fish_view IS NOT NULL AND EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name=split_part(fish_view,'.',2) AND column_name='genotype_rollup')
  THEN gene_col:='genotype_rollup';
  ELSE gene_col:=NULL; END IF;

  SELECT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='tank_pairs' AND column_name='fish_pair_code')
  INTO has_fp;

  IF to_regclass('public.v_tank_pairs') IS NOT NULL THEN
    EXECUTE 'DROP VIEW public.v_tank_pairs';
  END IF;

  dyn_sql := format($fmt$
    CREATE VIEW public.v_tank_pairs AS
    WITH base AS (
      SELECT
        tp.tank_pair_code,
        %1$s,
        tp.status,
        tp.created_by,
        tp.created_at,
        vtm.fish_code AS mom_fish_code,
        vtm.tank_code AS mom_tank_code,
        %2$s AS mom_genotype,
        vtf.fish_code AS dad_fish_code,
        vtf.tank_code AS dad_tank_code,
        %3$s AS dad_genotype
      FROM public.tank_pairs tp
      LEFT JOIN public.v_tanks vtm ON vtm.tank_uuid = tp.%4$I
      LEFT JOIN public.v_tanks vtf ON vtf.tank_uuid = tp.%5$I
      %6$s
      %7$s
    ),
    with_activity AS (
      SELECT
        b.*,
        (COALESCE(b.mom_fish_code,'') || ' × ' || COALESCE(b.dad_fish_code,'')) AS pair_fish,
        (COALESCE(b.mom_tank_code,'') || ' × ' || COALESCE(b.dad_tank_code,'')) AS pair_tanks,
        cx.cross_run_code       AS latest_cross_code,
        cx.cross_date           AS latest_cross_date,
        cl.clutch_instance_code AS latest_clutch_code,
        cl.created_at           AS latest_clutch_created_at
      FROM base b
      LEFT JOIN LATERAL (
        SELECT ci.cross_run_code, ci.cross_date, ci.created_at
        FROM public.cross_instances ci
        WHERE ci.tank_pair_code = b.tank_pair_code
        ORDER BY ci.created_at DESC NULLS LAST, ci.cross_date DESC NULLS LAST
        LIMIT 1
      ) cx ON TRUE
      LEFT JOIN LATERAL (
        SELECT cl.clutch_instance_code, cl.created_at
        FROM public.clutch_instances cl
        JOIN public.cross_instances ci2 ON ci2.id = cl.cross_instance_id
        WHERE ci2.tank_pair_code = b.tank_pair_code
        ORDER BY cl.created_at DESC NULLS LAST
        LIMIT 1
      ) cl ON TRUE
    )
    SELECT * FROM with_activity;
  $fmt$,
    CASE WHEN has_fp THEN 'tp.fish_pair_code AS fish_pair_code' ELSE 'NULL::text AS fish_pair_code' END,
    CASE WHEN fish_view IS NULL OR gene_col IS NULL THEN 'NULL::text'
         ELSE format('COALESCE(vfm.%I, '''')', gene_col) END,
    CASE WHEN fish_view IS NULL OR gene_col IS NULL THEN 'NULL::text'
         ELSE format('COALESCE(vfd.%I, '''')', gene_col) END,
    mcol, dcol,
    CASE WHEN fish_view IS NULL THEN '' ELSE format('LEFT JOIN %s vfm ON vtm.fish_code = vfm.fish_code', fish_view) END,
    CASE WHEN fish_view IS NULL THEN '' ELSE format('LEFT JOIN %s vfd ON vtf.fish_code = vfd.fish_code', fish_view) END
  );

  EXECUTE dyn_sql;
END;
$$;

COMMENT ON VIEW public.v_tank_pairs IS
  'Overview of tank pairings with mother/father fish+tanks, optional genotype (v_fish_*) and latest cross/clutch activity.';
