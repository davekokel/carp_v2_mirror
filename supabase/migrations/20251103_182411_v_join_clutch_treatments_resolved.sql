BEGIN;

CREATE OR REPLACE VIEW public.v_join_clutch_treatments_resolved AS
SELECT
  j.id,
  j.clutch_instance_id,
  j.treatment_id,
  t.name         AS treatment_name_resolved,
  t.plasmid_code AS treatment_code_resolved,
  t.kind_code,
  t.notes        AS treatment_notes,
  j.created_at
FROM public.join_clutch_treatments j
LEFT JOIN public.treatments t
  ON t.id = j.treatment_id;

COMMIT;
