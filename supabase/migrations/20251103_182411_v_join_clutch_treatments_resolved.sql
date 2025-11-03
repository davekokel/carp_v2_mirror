BEGIN;
CREATE OR REPLACE VIEW public.v_join_clutch_treatments_resolved AS
SELECT
  j.id,
  j.clutch_instance_id,
  j.treatment_id,
  COALESCE(t.name, j.treatment_name) AS treatment_name_resolved,
  COALESCE(t.plasmid_code, j.treatment_code) AS treatment_code_resolved,
  t.kind_code,
  t.notes AS treatment_notes,
  j.created_at
FROM public.join_clutch_treatments j
LEFT JOIN public.treatments t ON t.id = j.treatment_id;
COMMIT;
