BEGIN;

DO $$
DECLARE
  r record;
  def text;
  def_new text;
BEGIN
  FOR r IN
    SELECT p.oid
    FROM pg_proc p
    JOIN pg_namespace n ON n.oid = p.pronamespace
    WHERE n.nspname='public'
      AND pg_get_functiondef(p.oid) LIKE '%new_tank%'
  LOOP
    def := pg_get_functiondef(r.oid);
    def_new := replace(def, '''new_tank''', '''new''');
    IF def_new IS DISTINCT FROM def THEN
      EXECUTE def_new;
    END IF;
  END LOOP;
END$$;

COMMIT;
