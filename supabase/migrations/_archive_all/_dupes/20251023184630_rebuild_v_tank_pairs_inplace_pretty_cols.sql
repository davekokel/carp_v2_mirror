-- Rebuild public.v_tank_pairs in place with appended pretty columns,
-- rebind dependent views, and drop any obsolete v_tank_pairs_pretty.

DO $$
DECLARE
  v_bak text := 'v_tank_pairs__bak_' || to_char(clock_timestamp(), 'YYYYMMDDHH24MISS');
  dep   record;
BEGIN
  -- 1) Capture dependent VIEW definitions (as CREATE OR REPLACE … AS …)
  CREATE TEMP TABLE tmp_dep AS
  SELECT
      n.nspname AS view_schema,
      c.relname AS view_name,
      'CREATE OR REPLACE VIEW '
        || quote_ident(n.nspname) || '.' || quote_ident(c.relname)
        || E'\nAS\n' || pg_get_viewdef(c.oid, true) AS ddl
  FROM   pg_depend d
  JOIN   pg_rewrite   r ON r.oid = d.objid
  JOIN   pg_class     c ON c.oid = r.ev_class AND c.relkind = 'v'
  JOIN   pg_namespace n ON n.oid = c.relnamespace
  WHERE  d.refclassid = 'pg_class'::regclass
    AND  d.refobjid   = 'public.v_tank_pairs'::regclass;

  -- 2) Rename old view out of the way (dependent views now reference the bak name)
  EXECUTE 'ALTER VIEW public.v_tank_pairs RENAME TO ' || quote_ident(v_bak);

  -- 3) Create the NEW canonical view with explicit legacy columns + appended pretty helpers
  EXECUTE $create$
  CREATE VIEW public.v_tank_pairs AS
  WITH lc AS (
    SELECT
      c.fish_pair_id,
      c.clutch_code,
      c.expected_genotype,
      ROW_NUMBER() OVER (PARTITION BY c.fish_pair_id ORDER BY c.created_at DESC NULLS LAST) AS rn
    FROM public.clutches c
  )
  SELECT
    tp.id,
    tp.tank_pair_code,
    tp.tp_seq,
    tp.status,
    tp.role_orientation,
    tp.concept_id,
    tp.fish_pair_id,
    tp.created_by,
    tp.created_at,
    tp.updated_at,

    mt.tank_id                               AS mother_tank_id,
    COALESCE(tp.mom_tank_code, mt.tank_code) AS mom_tank_code,
    mt.fish_code                              AS mom_fish_code,
    tp.mom_genotype,

    dt.tank_id                               AS father_tank_id,
    COALESCE(tp.dad_tank_code, dt.tank_code) AS dad_tank_code,
    dt.fish_code                              AS dad_fish_code,
    tp.dad_genotype,

    -- appended pretty helpers
    COALESCE(mt.fish_code,'') || ' × ' || COALESCE(dt.fish_code,'') AS pair_fish,
    COALESCE(tp.mom_tank_code, mt.tank_code) || ' × ' ||
    COALESCE(tp.dad_tank_code, dt.tank_code)                         AS pair_tanks,

    CASE
      WHEN COALESCE(lc.expected_genotype,'') <> '' THEN lc.expected_genotype
      WHEN COALESCE(tp.mom_genotype,'') <> '' AND COALESCE(tp.dad_genotype,'') <> ''
           THEN tp.mom_genotype || ' × ' || tp.dad_genotype
      ELSE NULLIF(tp.mom_genotype,'')
    END                                                             AS pair_genotype,

    -- stable alias for UI/filters
    CASE
      WHEN COALESCE(lc.expected_genotype,'') <> '' THEN lc.expected_genotype
      WHEN COALESCE(tp.mom_genotype,'') <> '' AND COALESCE(tp.dad_genotype,'') <> ''
           THEN tp.mom_genotype || ' × ' || tp.dad_genotype
      ELSE NULLIF(tp.mom_genotype,'')
    END                                                             AS genotype,

    lc.clutch_code

  FROM public.$create$ || quote_ident(v_bak) || $create$ tp
  LEFT JOIN public.tanks mt ON mt.tank_id = tp.mother_tank_id
  LEFT JOIN public.tanks dt ON dt.tank_id = tp.father_tank_id
  LEFT JOIN lc ON lc.fish_pair_id = tp.fish_pair_id AND lc.rn = 1
  ORDER BY tp.created_at DESC NULLS LAST;
  $create$;

  -- 4) Recreate dependent views so they bind back to public.v_tank_pairs
  FOR dep IN SELECT ddl FROM tmp_dep LOOP
    EXECUTE dep.ddl;
  END LOOP;

  -- 5) Drop the backup view (no dependents remain on it)
  EXECUTE 'DROP VIEW IF EXISTS public.' || quote_ident(v_bak);

  -- 6) Drop any obsolete pretty wrapper
  IF EXISTS (
    SELECT 1 FROM information_schema.views
    WHERE  table_schema='public' AND table_name='v_tank_pairs_pretty'
  ) THEN
    EXECUTE 'DROP VIEW public.v_tank_pairs_pretty';
  END IF;
END
$$;

COMMENT ON VIEW public.v_tank_pairs IS
  'Snapshot-aware tank pairs, legacy columns preserved + UI helpers: pair_fish, pair_tanks, pair_genotype, genotype, clutch_code.';
