BEGIN;

-- Drop ONLY the FK from rnas(base_plasmid_code) -> plasmids(code) if it exists
DO $$
DECLARE
  fk_name text;
BEGIN
  SELECT c.conname
    INTO fk_name
  FROM   pg_constraint c
  JOIN   pg_class      r   ON r.oid = c.conrelid
  JOIN   pg_namespace  nr  ON nr.oid = r.relnamespace
  JOIN   pg_class      p   ON p.oid = c.confrelid
  JOIN   pg_namespace  np  ON np.oid = p.relnamespace
  WHERE  c.contype = 'f'
    AND  nr.nspname = 'public'
    AND  r.relname  = 'rnas'
    AND  np.nspname = 'public'
    AND  p.relname  = 'plasmids'
    AND  c.conkey   = ARRAY[
           (SELECT attnum
            FROM   pg_attribute
            WHERE  attrelid = r.oid
            AND    attname  = 'base_plasmid_code')
         ]::smallint[];

  IF fk_name IS NOT NULL THEN
    EXECUTE format('ALTER TABLE public.rnas DROP CONSTRAINT %I;', fk_name);
  END IF;
END$$;

-- Keep the column present & NOT NULL; no FK. (Idempotent reshaping)
ALTER TABLE public.rnas
  ALTER COLUMN base_plasmid_code SET NOT NULL;

COMMIT;
