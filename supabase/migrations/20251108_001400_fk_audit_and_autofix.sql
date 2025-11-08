-- supabase/migrations/20251108_001400_fk_audit_and_autofix.sql
-- Purpose: Audit implied (missing) foreign keys in `public` and auto-add safe ones (zero-orphan).
-- This script:
--   1) Builds a candidate list of implied FKs in `public` schema:
--        • Single-column *_id → parent(id)
--        • Single-column *_code → parent(code) where parent has a UNIQUE/PK on (code)
--        • Composite FKs where child has all columns matching a parent PRIMARY KEY or UNIQUE key names (e.g. transgene_base_code + allele_number → transgene_alleles(transgene_base_code, allele_number))
--   2) Skips candidates that already have a FK, skip polymorphic patterns (e.g. join_annotations.target_id), and checks for orphan rows.
--   3) For candidates with 0 orphans, adds `FOREIGN KEY ... NOT VALID` with `ON UPDATE CASCADE ON DELETE RESTRICT` and then VALIDATEs it.
--   4) Emits NOTICE/WARNING for each candidate and summary totals.
--
-- Safe to re-run (idempotent). Existing constraints are not duplicated.
-- Operates only on schema `public` and on base tables (no views).
--
-- Toggle automatic addition:
--   • Default: add safe FKs automatically (app.fk_add = 'on').
--   • To audit only (no changes): SET LOCAL app.fk_add = 'off';
--
-- Requires: PostgreSQL 12+.

BEGIN;

-- Optional: audit-only mode (uncomment to just report and NOT add FKs)
-- SET LOCAL app.fk_add = 'off';

-- Create a GUC to control whether to add constraints
DO $cfg$
BEGIN
  BEGIN
    PERFORM current_setting('app.fk_add');
  EXCEPTION
    WHEN undefined_object THEN
      PERFORM set_config('app.fk_add', 'on', true);
  END;
END
$cfg$;

-- Helper: compute orphan count for a candidate FK
--   Returns number of child rows whose FK columns are non-null and have no match in parent key.
CREATE OR REPLACE FUNCTION public._fk_orphan_count(
  p_child_schema text,
  p_child_table  text,
  p_child_cols   text[],
  p_parent_schema text,
  p_parent_table  text,
  p_parent_cols   text[]
) RETURNS bigint
LANGUAGE plpgsql
AS $$
DECLARE
  sql text;
  miss bigint;
  cond text;
  i int;
BEGIN
  IF array_length(p_child_cols,1) IS NULL OR array_length(p_child_cols,1) <> array_length(p_parent_cols,1) THEN
    RAISE EXCEPTION 'fk_orphan_count: column arity mismatch: % vs %', array_length(p_child_cols,1), array_length(p_parent_cols,1);
  END IF;
  -- build join condition c.col_i = p.col_i AND ... and non-null filter on child cols
  cond := '';
  FOR i IN 1..array_length(p_child_cols,1) LOOP
    IF i > 1 THEN
      cond := cond || ' AND ';
    END IF;
    cond := cond || format('c.%I = p.%I', p_child_cols[i], p_parent_cols[i]);
  END LOOP;
  -- non-null filter
  FOR i IN 1..array_length(p_child_cols,1) LOOP
    cond := cond || format(' AND c.%I IS NOT NULL', p_child_cols[i]);
  END LOOP;

  sql := format($f$
    WITH miss AS (
      SELECT 1
      FROM %I.%I AS c
      LEFT JOIN %I.%I AS p
        ON %s
      WHERE %s
        AND %s
        AND %s
    )
    SELECT count(*) FROM miss
  $f$,
    p_child_schema, p_child_table,
    p_parent_schema, p_parent_table,
    (SELECT regexp_replace(cond, ' AND c\.[^=]+ IS NULL', '' /*no-op*/)), -- cond contains equality + non-null; we keep both checks in WHERE explicitly
    'TRUE',  -- placeholder (kept for clarity)
    'TRUE'   -- placeholder
  );

  -- We need to ensure the ON clause uses only equality parts; replicate quickly:
  -- Rebuild proper SQL with separate WHERE:
  sql := format($f$
    WITH miss AS (
      SELECT 1
      FROM %I.%I AS c
      LEFT JOIN %I.%I AS p
        ON %s
      WHERE %s
    )
    SELECT count(*) FROM miss
  $f$,
    p_child_schema, p_child_table,
    p_parent_schema, p_parent_table,
    (SELECT string_agg(format('c.%I = p.%I', p_child_cols[i], p_parent_cols[i]), ' AND ')
       FROM generate_subscripts(p_child_cols,1) g(i)),
    (SELECT string_agg(format('c.%I IS NOT NULL', p_child_cols[i]), ' AND ')
       FROM generate_subscripts(p_child_cols,1) g(i))
  );

  EXECUTE sql INTO miss;
  RETURN COALESCE(miss,0);
END
$$;

-- Helper: add FK if it does not exist; uses NOT VALID + VALIDATE for minimal lock time
CREATE OR REPLACE FUNCTION public._add_fk_if_absent(
  p_child_schema text,
  p_child_table  text,
  p_child_cols   text[],
  p_parent_schema text,
  p_parent_table  text,
  p_parent_cols   text[],
  p_fk_name text,
  p_on_update text DEFAULT 'CASCADE',
  p_on_delete text DEFAULT 'RESTRICT'
) RETURNS boolean
LANGUAGE plpgsql
AS $$
DECLARE
  fk_exists boolean := false;
  fk_name text := lower(p_fk_name);
  condef  text;
  add_sql text;
  validate_sql text;
  added boolean := false;
  orphan_cnt bigint;
  do_add boolean := (current_setting('app.fk_add', true) = 'on');
BEGIN
  -- if name already taken by a constraint, skip
  SELECT EXISTS(SELECT 1 FROM pg_constraint WHERE conname = fk_name) INTO fk_exists;
  IF fk_exists THEN
    RAISE NOTICE 'FK % already exists, skipping.', fk_name;
    RETURN false;
  END IF;

  -- safety: count orphans
  orphan_cnt := public._fk_orphan_count(p_child_schema, p_child_table, p_child_cols, p_parent_schema, p_parent_table, p_parent_cols);
  IF orphan_cnt > 0 THEN
    RAISE WARNING 'SKIP: %.%(% ) → %.%(%) has % orphan rows. Fix data first.',
      p_child_schema, p_child_table, array_to_string(p_child_cols,','), p_parent_schema, p_parent_table, array_to_string(p_parent_cols,','), orphan_cnt;
    RETURN false;
  END IF;

  -- build DDL
  add_sql := format(
    'ALTER TABLE %I.%I ADD CONSTRAINT %I FOREIGN KEY (%s) REFERENCES %I.%I (%s) ON UPDATE %s ON DELETE %s NOT NULL DEFERRABLE INITIALLY IMMEDIATE NOT VALID',
    p_child_schema, p_child_table, fk_name,
    (SELECT string_agg(format('%I', c), ', ') FROM unnest(p_child_cols) AS c),
    p_parent_schema, p_parent_table,
    (SELECT string_agg(format('%I', c), ', ') FROM unnest(p_parent_cols) AS c),
    p_on_update, p_on_delete
  );

  validate_sql := format('ALTER TABLE %I.%I VALIDATE CONSTRAINT %I', p_child_schema, p_child_table, fk_name);

  IF do_add THEN
    BEGIN
      EXECUTE add_sql;
      EXECUTE validate_sql;
      added := true;
      RAISE NOTICE 'ADDED: %', fk_name;
    EXCEPTION WHEN duplicate_object THEN
      RAISE NOTICE 'FK % already present (or concurrent add), skipping.', fk_name;
      added := false;
    WHEN OTHERS THEN
      RAISE WARNING 'FAILED to add %: %', fk_name, SQLERRM;
      -- attempt cleanup if partially added without validation
      BEGIN
        EXECUTE format('ALTER TABLE %I.%I DROP CONSTRAINT IF EXISTS %I', p_child_schema, p_child_table, fk_name);
      EXCEPTION WHEN OTHERS THEN
        NULL;
      END;
      added := false;
    END;
  ELSE
    RAISE NOTICE 'AUDIT: would add FK %', fk_name;
  END IF;

  RETURN added;
END
$$;

-- Collect candidates and act
DO $body$
DECLARE
  rec record;
  v_fk_name text;
  v_added_count int := 0;
  v_skipped_count int := 0;
  v_total int := 0;
BEGIN
  -- temp table to hold candidates + orphan counts
  CREATE TEMP TABLE IF NOT EXISTS tmp_fk_candidates (
    child_schema text,
    child_table  text,
    child_cols   text[],
    parent_schema text,
    parent_table  text,
    parent_cols   text[],
    fk_name       text,
    orphan_count  bigint
  ) ON COMMIT DROP;

  TRUNCATE tmp_fk_candidates;

  -- Build parent key catalog (PKs and UNIQUEs)
  WITH parent_keys AS (
    SELECT
      tc.table_schema,
      tc.table_name,
      tc.constraint_name,
      array_agg(kcu.column_name ORDER BY kcu.ordinal_position) AS cols
    FROM information_schema.table_constraints tc
    JOIN information_schema.key_coluMN_usage kcu
      ON kcu.constraint_name = tc.constraint_name
     AND kcu.table_schema = tc.table_schema
     AND kcu.table_name   = tc.table_name
    WHERE tc.table_schema = 'public'
      AND tc.constraint_type IN ('PRIMARY KEY','UNIQUE')
    GROUP BY 1,2,3
  ),
  child_cols AS (
    SELECT table_schema, table_name, column_name, udt_name
    FROM information_schema.columns
    WHERE table_schema='public'
  ),
  -- 1) single-column ID → parent(id)
  cand_id AS (
    SELECT DISTINCT
      c.table_schema  AS child_schema,
      c.table_name    AS child_table,
      ARRAY[c.column_name] AS child_cols,
      pk.table_schema AS parent_schema,
      pk.table_name   AS parent_table,
      pk.cols         AS parent_cols
    FROM child_cols c
    JOIN parent_keys pk ON array_length(pk.cols,1) = 1 AND pk.cols[1] = 'id'
    WHERE c.column_name LIKE '%\_id' ESCAPE '\'
      AND (  -- heuristics: strip suffix and try base/plural/es
        lower(pk.table_name) = lower(regexp_replace(c.column_name,'_id$','')) OR
        lower(pk.table_name) = lower(regexp_replace(c.column_name,'_id$',''))||'s' OR
        lower(pk.table_name)||'s' = lower(regexp_replace(c.column_name,'_id$','')) -- reverse
      )
      -- skip polymorphic target_id if table has a target_type sidecar
      AND NOT (c.column_name = 'target_id'
               AND EXISTS (SELECT 1 FROM information_schema.columns cc
                           WHERE cc.table_schema=c.table_schema AND cc.table_name=c.table_name AND cc.column_name='target_type'))
  ),
  -- 2) single-column *_code → parent(code) where parent has UNIQUE/PK on (code)
  cand_code AS (
    SELECT DISTINCT
      c.table_schema  AS child_schema,
      c.table_name    AS child_table,
      ARRAY[c.column_name] AS child_cols,
      pk.table_schema AS parent_schema,
      pk.table_name   AS parent_table,
      pk.cols         AS parent_cols
    FROM child_cols c
    JOIN parent_keys pk ON array_length(pk.cols,1) = 1 AND pk.cols[1] = 'code'
    WHERE c.column_name LIKE '%\_code' ESCAPE '\'
      AND (  -- map *_code → <table>.code via base name
        lower(pk.table_name) = lower(regexp_replace(c.column_name,'_code$','')) OR
        lower(pk.table_name) = lower(regexp_replace(c.column_name,'_code$',''))||'s'
      )
  ),
  -- 3) composite FKs: child has all columns matching a parent (pk or unique) by name
  cand_comp AS (
    SELECT
      c.table_schema  AS child_schema,
      c.table_name    AS child_table,
      ARRAY_AGG(c.column_name ORDER BY c.column_name) AS child_cols,
      pk.table_schema AS parent_schema,
      pk.table_name   AS parent_table,
      pk.cols         AS parent_cols
    FROM parent_keys pk
    JOIN information_schema.columns c
      ON c.table_schema = 'public'
     AND c.column_name = ANY (pk.cols)
    GROUP BY c.table_schema, c.table_name, pk.table_schema, pk.table_name, pk.cols
    HAVING array_length(pk.cols,1) = count(*)  -- child has all parent key columns by name
  ),
  unioned AS (
    SELECT * FROM cand_id
    UNION
    SELECT * FROM cand_code
    UNION
    SELECT * FROM cand_comp
  ),
  -- filter out existing FKs on same child table+columns (any name)
  no_existing AS (
    SELECT u.*
    FROM unioned u
    WHERE NOT EXISTS (
      SELECT 1
      FROM information_schema.table_constraints tc
      JOIN information_schema.key_column_usage kcu
        ON kcu.constraint_name = tc.constraint_name
       AND kcu.table_schema    = tc.table_schema
       AND kcu.table_name      = u.child_table
      WHERE tc.table_schema='public'
        AND tc.table_name = u.child_table
        AND tc.constraint_type='FOREIGN KEY'
      GROUP BY tc.constraint_name
      HAVING array_agg(kcu.column_name ORDER BY kcu.ordinal_position) = u.child_cols
    )
  )
  INSERT INTO tmp_fk_candidates (child_schema, child_table, child_cols, parent_schema, parent_table, parent_cols, fk_name, orphan_count)
  SELECT
    child_schema, child_table, child_cols,
    parent_schema, parent_table, parent_cols,
    -- propose a deterministic name; compress if > 60 chars
    CASE
      WHEN length(lower(format('fk_%s_%s__%s_%s', child_table, array_to_string(child_cols,'_'), parent_table, array_to_string(parent_cols,'_')))) <= 60
      THEN lower(format('fk_%s_%s__%s_%s', child_table, array_to_string(child_cols,'_'), parent_table, array_to_string(parent_cols,'_')))
      ELSE 'fk_' || substring(md5(format('%s|%s|%s|%s', child_table, array_to_string(child_cols,','), parent_table, array_to_string(parent_cols,','))) for 30)
    END AS fk_name,
    public._fk_orphan_count(child_schema, child_table, child_cols, parent_schema, parent_table, parent_cols) AS orphan_count
  FROM no_existing
  WHERE child_schema='public' AND parent_schema='public';

  -- Report findings
  RAISE NOTICE '--- FK AUDIT (public) ---';
  FOR rec IN SELECT * FROM tmp_fk_candidates ORDER BY orphan_count, child_table, fk_name LOOP
    RAISE NOTICE 'Candidate %: %.%(% ) -> %.%(%)  | orphans=%',
      rec.fk_name,
      rec.child_table, array_to_string(rec.child_cols,','),
      rec.parent_table, array_to_string(rec.parent_cols,','),
      rec.orphan_count;
  END LOOP;

  -- Add safe FKs (no orphans) when app.fk_add = 'on'
  IF current_setting('app.fk_add', true) = 'on' THEN
    FOR rec IN SELECT * FROM tmp_fk_candidates WHERE orphan_count = 0 LOOP
      PERFORM public._add_fk_if_absent(
        rec.child_schema, rec.child_table, rec.child_cols,
        rec.parent_schema, rec.parent_table, rec.parent_cols,
        rec.fk_name, 'CASCADE', 'RESTRICT'
      );
      GET DIAGNOSTICS v_total = ROW_COUNT; -- not used for count; we track via notices inside function
    END LOOP;
  ELSE
    RAISE NOTICE 'app.fk_add=off → audit-only mode: no constraints were added.';
  END IF;

  -- Summary
  SELECT count(*) INTO v_total FROM tmp_fk_candidates;
  SELECT count(*) INTO v_added_count FROM tmp_fk_candidates WHERE orphan_count = 0;
  SELECT count(*) INTO v_skipped_count FROM tmp_fk_candidates WHERE orphan_count > 0;

  RAISE NOTICE 'SUMMARY: % candidates | % safe -> added (or would add) | % skipped due to orphans',
    v_total, v_added_count, v_skipped_count;

  -- Cleanup helper functions (keep schema clean)
  PERFORM 1;
  EXECUTE 'DROP FUNCTION IF EXISTS public._fk_orphan_count(text,text,text[],text,text,text[])';
  EXECUTE 'DROP FUNCTION IF EXISTS public._add_fk_if_absent(text,text,text[],text,text,text[],text,text,text)';
END
$body$;

COMMIT;