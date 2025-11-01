DO $$
DECLARE
  trash text := 'trash_carp';
  keep  text[] := ARRAY[
    'fish','tanks','fish_tank_memberships','fish_transgene_alleles',
    'transgene_alleles','transgenes','fish_year_counters',
    'cross_plans','cross_plan_runs','cross_plan_treatments','cross_plan_genotype_alleles',
    'cross_instances','clutches','clutch_instances',
    'tank_pairs','tank_status_history',
    'containers','label_jobs','label_items',
    'transgene_allele_registry','mounts','plasmids','clutch_materials'
  ];
  rec record;
BEGIN
  EXECUTE format('CREATE SCHEMA IF NOT EXISTS %I', trash);

  FOR rec IN
    WITH pub AS (
      SELECT c.oid, c.relname
      FROM pg_class c
      JOIN pg_namespace n ON n.oid=c.relnamespace
      WHERE c.relkind IN ('r','p') AND n.nspname='public'
    ),
    not_kept AS (
      SELECT p.*
      FROM pub p
      WHERE NOT (p.relname = ANY(keep))
    ),
    view_deps AS (
      SELECT d.refobjid AS oid
      FROM pg_depend d
      JOIN pg_class v ON v.oid = d.objid
      WHERE v.relkind IN ('v','m')
    ),
    normal_deps AS (
      SELECT d.refobjid AS oid, count(*) AS n
      FROM pg_depend d
      WHERE d.deptype = 'n'
      GROUP BY d.refobjid
    )
    SELECT nk.relname
    FROM not_kept nk
    LEFT JOIN view_deps vd ON vd.oid = nk.oid
    LEFT JOIN normal_deps nd ON nd.oid = nk.oid
    WHERE vd.oid IS NULL            -- no view depends on it
      AND COALESCE(nd.n,0) = 0      -- no normal deps (fkeys/triggers)
    ORDER BY nk.relname
  LOOP
    BEGIN
      IF to_regclass(format('public.%I', rec.relname)) IS NOT NULL
         AND to_regclass(format('%I.%I', trash, rec.relname)) IS NULL THEN
        EXECUTE format('ALTER TABLE public.%I SET SCHEMA %I', rec.relname, trash);
      END IF;
    EXCEPTION WHEN OTHERS THEN
      -- best effort; skip any problematic table
      NULL;
    END;
  END LOOP;
END $$;
