BEGIN;

-- 1) Helpful index for treated-clutch annotations
CREATE INDEX IF NOT EXISTS ix_join_annotations_tclutch
  ON public.join_annotations (target_type, target_id, created_at DESC);

-- 2) Backfill: copy existing 'clutch' annotations to the baseline treated group T(<CI>)-0
--    Only copy if we haven't already written a treated_clutch version of the same row.
WITH src AS (
  SELECT
    ja.*,
    tc.id AS treated_clutch_id
  FROM public.join_annotations ja
  JOIN public.clutch_instances ci
    ON ci.id = ja.target_id::uuid
  JOIN public.treated_clutches tc
    ON tc.clutch_instance_id = ci.id
   AND tc.treated_clutch_code = 'T('||ci.clutch_instance_code||')-0'
  WHERE ja.target_type = 'clutch'
),
dupe_check AS (
  SELECT
    s.target_id, s.annotation_id, s.value_num, s.value_text, s.created_at, s.created_by,
    s.treated_clutch_id
  FROM src s
  LEFT JOIN public.join_annotations j2
    ON j2.target_type = 'treated_clutch'
   AND j2.target_id   = s.treated_clutch_id
   AND j2.annotation_id = s.annotation_id
   AND COALESCE(j2.value_num,0) = COALESCE(s.value_num,0)
   AND COALESCE(j2.value_text,'') = COALESCE(s.value_text,'')
  WHERE j2.id IS NULL
)
INSERT INTO public.join_annotations (target_type, target_id, annotation_id, value_num, value_text, created_by, created_at)
SELECT
  'treated_clutch',
  treated_clutch_id::text,
  annotation_id,
  value_num,
  value_text,
  created_by,
  created_at
FROM dupe_check;

COMMIT;
