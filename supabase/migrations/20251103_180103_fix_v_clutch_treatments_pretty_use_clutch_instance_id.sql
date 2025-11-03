BEGIN;
DROP VIEW IF EXISTS public.v_clutch_treatments_pretty;
CREATE VIEW public.v_clutch_treatments_pretty AS
SELECT
  j.id::text AS join_id,
  j.clutch_instance_id::text AS clutch_id,
  t.id::text AS treatment_id,
  t.kind_code,
  t.name AS treatment_name,
  t.plasmid_code,
  t.notes AS treatment_notes,
  j.created_at
FROM public.join_clutch_treatments j
JOIN public.treatments t ON t.id=j.treatment_id;
COMMIT;
