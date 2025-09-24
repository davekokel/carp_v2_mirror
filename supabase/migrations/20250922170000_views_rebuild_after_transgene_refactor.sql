DO $$
DECLARE
  v      text;
  vlist  text[];
BEGIN
  -- 1) Gather dependent views (anything referencing public.transgenes)
  SELECT array_agg(quote_ident(n.nspname) || '.' || quote_ident(c.relname))
  INTO vlist
  FROM pg_depend d
  JOIN pg_rewrite  r  ON r.oid = d.objid
  JOIN pg_class    c  ON c.oid = r.ev_class AND c.relkind = 'v'
  JOIN pg_namespace n ON n.oid = c.relnamespace
  JOIN pg_class    t  ON t.oid = d.refobjid
  JOIN pg_namespace nt ON nt.oid = t.relnamespace
  WHERE nt.nspname = 'public' AND t.relname = 'transgenes';

  -- 2) Drop those views (we already keep view SQL in repo, so safe)
  IF vlist IS NOT NULL THEN
    FOREACH v IN ARRAY vlist LOOP
      EXECUTE format('DROP VIEW IF EXISTS %s', v);
    END LOOP;
  END IF;
END$$ LANGUAGE plpgsql;

-- 3) *** your table changes go here ***
-- e.g. ALTER TABLE public.transgenes RENAME COLUMN base_code TO transgene_base_code;

-- 4) Recreate views (either paste CREATEs here, or keep as separate migrations)
-- Example:
-- CREATE OR REPLACE VIEW public.v_fish_overview_v1 AS
-- <paste the SELECT body here>;
