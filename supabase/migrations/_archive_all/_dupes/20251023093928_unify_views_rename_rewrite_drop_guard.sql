BEGIN;

-- 1) Rename vw_* -> v_* if the v_* doesn't already exist.
DO $$
BEGIN
  IF to_regclass('public.v_fish_overview_with_label') IS NULL
     AND to_regclass('public.vw_fish_overview_with_label') IS NOT NULL THEN
    ALTER VIEW public.vw_fish_overview_with_label RENAME TO v_fish_overview_with_label;
  END IF;

  IF to_regclass('public.v_fish_standard') IS NULL
     AND to_regclass('public.vw_fish_standard') IS NOT NULL THEN
    ALTER VIEW public.vw_fish_standard RENAME TO v_fish_standard;
  END IF;

  IF to_regclass('public.v_plasmids_overview') IS NULL
     AND to_regclass('public.vw_plasmids_overview') IS NOT NULL THEN
    ALTER VIEW public.vw_plasmids_overview RENAME TO v_plasmids_overview;
  END IF;
END$$;

-- 2) Recreate vw_* shims (so dependents won’t break while we rewrite them)
--    These are harmless no-ops if the shims already exist with the same body.
DO $$
BEGIN
  IF to_regclass('public.vw_fish_overview_with_label') IS NULL
     AND to_regclass('public.v_fish_overview_with_label') IS NOT NULL THEN
    CREATE OR REPLACE VIEW public.vw_fish_overview_with_label AS
    SELECT * FROM public.v_fish_overview_with_label;
  END IF;

  IF to_regclass('public.vw_fish_standard') IS NULL
     AND to_regclass('public.v_fish_standard') IS NOT NULL THEN
    CREATE OR REPLACE VIEW public.vw_fish_standard AS
    SELECT * FROM public.v_fish_standard;
  END IF;

  IF to_regclass('public.vw_plasmids_overview') IS NULL
     AND to_regclass('public.v_plasmids_overview') IS NOT NULL THEN
    CREATE OR REPLACE VIEW public.vw_plasmids_overview AS
    SELECT * FROM public.v_plasmids_overview;
  END IF;
END$$;

-- 3) Rewrite all public views whose definitions still reference vw_* -> v_*
CREATE TEMP TABLE _rename_map(old TEXT, new TEXT) ON COMMIT DROP;
INSERT INTO _rename_map(old,new) VALUES
  ('vw_fish_overview_with_label','v_fish_overview_with_label'),
  ('vw_fish_standard','v_fish_standard'),
  ('vw_plasmids_overview','v_plasmids_overview');

DO $$
DECLARE
  r RECORD;
  def TEXT;
  def_new TEXT;
  m RECORD;
BEGIN
  FOR r IN
    SELECT schemaname, viewname
    FROM pg_views
    WHERE schemaname='public'
  LOOP
    def := pg_get_viewdef((quote_ident(r.schemaname)||'.'||quote_ident(r.viewname))::regclass, true);
    def_new := def;
    FOR m IN SELECT * FROM _rename_map LOOP
      -- Replace both qualified and unqualified mentions
      def_new := replace(def_new, 'public.'||m.old, 'public.'||m.new);
      def_new := replace(def_new, m.old, m.new);
    END LOOP;
    IF def_new IS DISTINCT FROM def THEN
      EXECUTE 'CREATE OR REPLACE VIEW '
              || quote_ident(r.schemaname) || '.' || quote_ident(r.viewname)
              || ' AS ' || def_new;
    END IF;
  END LOOP;
END$$;

-- 4) Ensure no dependents remain, then drop the shims
DO $$
DECLARE
  leftovers TEXT[];
BEGIN
  SELECT array_agg(DISTINCT vtu.view_name)
  INTO leftovers
  FROM information_schema.view_table_usage vtu
  WHERE vtu.view_schema='public'
    AND vtu.table_name IN ('vw_fish_overview_with_label','vw_fish_standard','vw_plasmids_overview');

  IF leftovers IS NOT NULL THEN
    RAISE EXCEPTION 'Cannot drop vw_*; still referenced by: %', leftovers;
  END IF;
END$$;

DROP VIEW IF EXISTS public.vw_fish_overview_with_label;
DROP VIEW IF EXISTS public.vw_fish_standard;
DROP VIEW IF EXISTS public.vw_plasmids_overview;

-- 5) Guardrail: disallow future vw_* views in public
DROP EVENT TRIGGER IF EXISTS enforce_public_view_prefix;
DROP FUNCTION IF EXISTS public.enforce_view_prefix_v();

CREATE FUNCTION public.enforce_view_prefix_v() RETURNS event_trigger
LANGUAGE plpgsql
AS $$
DECLARE
  rec record;
BEGIN
  FOR rec IN
    SELECT *
    FROM pg_event_trigger_ddl_commands()
  LOOP
    IF rec.object_type = 'view'
       AND rec.schema_name = 'public'
       AND rec.object_identity ~* E'^public\\.vw_'
    THEN
      RAISE EXCEPTION 'Disallowed view prefix vw_: %', rec.object_identity;
    END IF;
  END LOOP;
END
$$;

CREATE EVENT TRIGGER enforce_public_view_prefix
ON ddl_command_end
WHEN TAG IN ('CREATE VIEW','CREATE MATERIALIZED VIEW','ALTER VIEW','ALTER VIEW ALL IN SCHEMA')
EXECUTE PROCEDURE public.enforce_view_prefix_v();

COMMIT;
