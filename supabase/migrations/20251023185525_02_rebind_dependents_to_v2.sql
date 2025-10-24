-- Rewrites any DB VIEW that currently references public.v_tank_pairs so it points to public.v_tank_pairs_v2 instead.

DO $$
DECLARE
  rec RECORD;
  def text;
  newdef text;
BEGIN
  FOR rec IN
    SELECT n.nspname AS schemaname, c.relname AS viewname, pg_get_viewdef(c.oid, true) AS def
    FROM   pg_depend d
    JOIN   pg_rewrite   r ON r.oid = d.objid
    JOIN   pg_class     c ON c.oid = r.ev_class AND c.relkind = 'v'
    JOIN   pg_namespace n ON n.oid = c.relnamespace
    WHERE  d.refclassid = 'pg_class'::regclass
       AND d.refobjid   = 'public.v_tank_pairs'::regclass
  LOOP
    -- Try to replace both qualified and unqualified references
    newdef := replace(rec.def, 'public.v_tank_pairs', 'public.v_tank_pairs_v2');
    newdef := regexp_replace(newdef, '(^|[^A-Za-z0-9_])v_tank_pairs([^A-Za-z0-9_])', '\1public.v_tank_pairs_v2\2', 'g');

    EXECUTE 'CREATE OR REPLACE VIEW '
            || quote_ident(rec.schemaname) || '.' || quote_ident(rec.viewname)
            || E'\nAS\n' || newdef;
  END LOOP;
END
$$;
