BEGIN;

-- Schema-aware copy of clutch-level annotations -> treated_clutch.
-- Works whether treated_clutches links by clutch_instance_id (uuid) or clutch_code (text).
DO $$
DECLARE
  has_ci_id   boolean;
  has_ci_code boolean;
  sql_text    text;
BEGIN
  SELECT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='treated_clutches' AND column_name='clutch_instance_id'
  ) INTO has_ci_id;

  SELECT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='treated_clutches' AND column_name='clutch_code'
  ) INTO has_ci_code;

  IF NOT has_ci_id AND NOT has_ci_code THEN
    RAISE EXCEPTION 'treated_clutches must have either clutch_instance_id (uuid) or clutch_code (text)';
  END IF;

  sql_text := '
    WITH src AS (
      SELECT
        tc.id                          AS treated_clutch_id,   -- uuid
        ja.annotation_id,                                     -- uuid
        ja.value_num,
        ja.value_text,
        COALESCE(ja.created_by, '''') AS created_by,
        ja.created_at
      FROM public.treated_clutches tc
      JOIN public.clutch_instances ci ON ' ||
      CASE
        WHEN has_ci_id   THEN 'ci.id = tc.clutch_instance_id '
        WHEN has_ci_code THEN 'ci.clutch_instance_code = tc.clutch_code '
      END ||
      'JOIN public.join_annotations ja
         ON ja.target_type = ''clutch'' AND ja.target_id = ci.id
      WHERE ja.annotation_id IN (
        SELECT id FROM public.annotations
        WHERE kind_code IN (''red_intensity'',''green_intensity'',''green_frequency'',''red_frequency'',''n_animals'',''notes'')
      )
    ),
    dupe_filtered AS (
      SELECT s.*
      FROM src s
      LEFT JOIN public.join_annotations j
        ON j.target_type   = ''treated_clutch''
       AND j.target_id     = s.treated_clutch_id   -- uuid; no cast
       AND j.annotation_id = s.annotation_id
       AND (j.value_num  IS NOT DISTINCT FROM s.value_num)
       AND (j.value_text IS NOT DISTINCT FROM s.value_text)
      WHERE j.id IS NULL
    )
    INSERT INTO public.join_annotations
      (target_type,      target_id,          annotation_id, value_num, value_text, created_by, created_at)
    SELECT
      ''treated_clutch'', treated_clutch_id, annotation_id, value_num, value_text, created_by, created_at
    FROM dupe_filtered
  ';

  EXECUTE sql_text;
END $$;

COMMIT;
