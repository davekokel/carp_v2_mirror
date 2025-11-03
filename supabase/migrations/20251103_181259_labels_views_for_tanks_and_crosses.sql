BEGIN;

CREATE OR REPLACE VIEW public.v_labels_for_tanks AS
SELECT
  COALESCE(NULLIF(li.payload->>'tank_id',''),
           NULLIF(li.payload->>'tank_uuid',''),
           NULLIF(li.payload->>'target_id',''))::uuid              AS tank_id,
  li.id::text                                                     AS label_item_id,
  lj.id::text                                                     AS job_id,
  COALESCE(NULLIF(li.payload->>'label',''),
           NULLIF(li.payload->>'text',''))                        AS label_text,
  li.created_at
FROM public.label_items li
JOIN public.label_jobs  lj ON lj.id = li.job_id
WHERE lower(lj.kind) IN ('tank','tanks','tank_label','tank_labels');

CREATE OR REPLACE VIEW public.v_labels_for_crosses AS
SELECT
  COALESCE(NULLIF(li.payload->>'cross_id',''),
           NULLIF(li.payload->>'cross_uuid',''),
           NULLIF(li.payload->>'target_id',''))::uuid             AS cross_id,
  li.id::text                                                     AS label_item_id,
  lj.id::text                                                     AS job_id,
  COALESCE(NULLIF(li.payload->>'label',''),
           NULLIF(li.payload->>'text',''))                        AS label_text,
  li.created_at
FROM public.label_items li
JOIN public.label_jobs  lj ON lj.id = li.job_id
WHERE lower(lj.kind) IN ('cross','crosses','cross_label','cross_labels');

COMMIT;
