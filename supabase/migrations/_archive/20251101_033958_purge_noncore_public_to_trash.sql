-- Move non-core public tables into trash_carp (safe; no drops).
-- Re-runnable and idempotent. Runs up to 5 passes to catch newly-free tables.

DO $plpgsql$
DECLARE
  pass int := 1;
  moved_in_pass int := 0;
BEGIN
  -- Ensure quarantine exists
  EXECUTE 'CREATE SCHEMA IF NOT EXISTS trash_carp';

  <<again>>
  moved_in_pass := 0;

  WITH core(name) AS (
    VALUES
      -- CORE entities
      ('fish'),('tanks'),('tank_pairs'),
      ('clutches'),('clutch_instances'),
      ('containers'),('mounts'),
      ('plasmids'),('fluors'),('tags'),('fusions'),
      ('transgenes'),('transgene_alleles'),
      ('fish_tank_memberships'),('fish_transgene_alleles'),
      ('transgene_allele_registry'),
      ('label_jobs'),('label_items'),
      ('tank_status_history'),('fish_year_counters'),
      -- keep both until we fully consolidate: conceptual “crosses” and realized runs
      ('crosses'),('cross_instances'),
      -- generic clutch link
      ('clutch_materials')
  ),
  pub_rel AS (
    SELECT c.oid, c.relname
    FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE c.relkind IN ('r','p') AND n.nspname = 'public'
  ),
  candidates AS (
    SELECT p.oid, p.relname
    FROM pub_rel p
    LEFT JOIN core k ON k.name = p.relname
    WHERE k.name IS NULL
  ),
  -- Any dependency *from* a public view or table will block
  deps AS (
    SELECT d.refobjid AS oid,
           COUNT(*) FILTER (WHERE vn.nspname='public' AND vc.relkind IN ('v','m')) AS dep_public_views,
           COUNT(*) FILTER (WHERE tn.nspname='public' AND con.contype='f')        AS dep_public_fks
    FROM pg_depend d
    LEFT JOIN pg_class vc ON vc.oid = d.objid
    LEFT JOIN pg_namespace vn ON vn.oid = vc.relnamespace
    LEFT JOIN pg_constraint con ON con.oid = d.objid
    LEFT JOIN pg_class tc  ON tc.oid  = con.conrelid
    LEFT JOIN pg_namespace tn ON tn.oid = tc.relnamespace
    GROUP BY d.refobjid
  ),
  movable AS (
    SELECT c.relname
    FROM candidates c
    LEFT JOIN deps d ON d.oid = c.oid
    WHERE COALESCE(d.dep_public_views,0)=0
      AND COALESCE(d.dep_public_fks,0)=0
      -- don't try to move if already in trash
      AND to_regclass('trash_carp.'||c.relname) IS NULL
  )
  SELECT 1
  FROM movable
  ORDER BY 1;
  -- ^ just prime the CTEs; real work below

  FOR r IN SELECT relname FROM movable LOOP
    BEGIN
      IF to_regclass(format('public.%I', r.relname)) IS NOT NULL THEN
        EXECUTE format('ALTER TABLE public.%I SET SCHEMA trash_carp', r.relname);
        moved_in_pass := moved_in_pass + 1;
      END IF;
    EXCEPTION WHEN duplicate_table THEN
      -- someone/earlier pass already moved it – ignore
      CONTINUE;
    WHEN undefined_table THEN
      CONTINUE;
    END;
  END LOOP;

  IF moved_in_pass > 0 AND pass < 5 THEN
    pass := pass + 1;
    GOTO again;
  END IF;
END
$plpgsql$;

-- Optional: quick visibility helpers (no schema changes)
-- SELECT n.nspname AS schema, COUNT(*) AS tables
-- FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
-- WHERE c.relkind IN ('r','p') AND n.nspname IN ('public','trash_carp')
-- GROUP BY 1 ORDER BY 1;
