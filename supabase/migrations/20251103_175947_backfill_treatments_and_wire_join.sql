BEGIN;

-- Keep the uniqueness index if not present (harmless if it already exists)
CREATE UNIQUE INDEX IF NOT EXISTS uq_treatments_kind_name_plasmid
  ON public.treatments (kind_code, name, COALESCE(plasmid_code,''));

-- Recreate the pretty view to use normalized columns only
DROP VIEW IF EXISTS public.v_clutch_treatments_pretty;
CREATE VIEW public.v_clutch_treatments_pretty AS
SELECT
  j.id::text         AS join_id,
  j.clutch_instance_id::text AS clutch_id,
  t.id::text         AS treatment_id,
  t.kind_code,
  t.name             AS treatment_name,
  t.plasmid_code,
  t.notes            AS treatment_notes,
  j.created_at
FROM public.join_clutch_treatments j
JOIN public.treatments t ON t.id = j.treatment_id;

COMMIT;
