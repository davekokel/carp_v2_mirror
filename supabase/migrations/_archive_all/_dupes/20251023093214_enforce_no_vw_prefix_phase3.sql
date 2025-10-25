BEGIN;

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
