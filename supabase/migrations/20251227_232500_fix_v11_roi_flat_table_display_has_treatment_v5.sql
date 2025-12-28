DO $$
DECLARE
  cols text;
BEGIN
  WITH flat AS (
    SELECT
      c.ordinal_position,
      c.column_name,
      c.data_type,
      c.udt_name
    FROM information_schema.columns c
    WHERE c.table_schema = 'public'
      AND c.table_name = 'v11_roi_flat_table_display'
  ),
  src AS (
    SELECT c.column_name
    FROM information_schema.columns c
    WHERE c.table_schema = 'public'
      AND c.table_name = 'v11_roi_treatment_table_display'
  ),
  rendered AS (
    SELECT
      f.ordinal_position,
      CASE
        WHEN f.column_name = 'has_treatment' THEN
          '(
            (t.treated_clutch_code IS NOT NULL AND btrim(t.treated_clutch_code) <> '''')
            OR (t.treatment_code IS NOT NULL AND btrim(t.treatment_code) <> '''')
            OR (t.plasmids_display IS NOT NULL AND btrim(t.plasmids_display) <> '''')
            OR (t.rnas_display IS NOT NULL AND btrim(t.rnas_display) <> '''')
            OR (t.dyes_display IS NOT NULL AND btrim(t.dyes_display) <> '''')
          ) AS has_treatment'
        WHEN EXISTS (SELECT 1 FROM src s WHERE s.column_name = f.column_name) THEN
          format('t.%I', f.column_name)
        ELSE
          CASE
            WHEN f.data_type = 'USER-DEFINED' THEN
              format('NULL::%s AS %I', f.udt_name, f.column_name)
            ELSE
              format('NULL::%s AS %I', f.data_type, f.column_name)
          END
      END AS expr
    FROM flat f
  )
  SELECT string_agg(r.expr, ', ' ORDER BY r.ordinal_position)
  INTO cols
  FROM rendered r;

  IF cols IS NULL THEN
    RAISE EXCEPTION 'view public.v11_roi_flat_table_display not found (or has no columns)';
  END IF;

  EXECUTE 'CREATE OR REPLACE VIEW public.v11_roi_flat_table_display AS SELECT ' || cols || ' FROM public.v11_roi_treatment_table_display t';
END $$;
