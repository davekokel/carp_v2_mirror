BEGIN;

CREATE UNIQUE INDEX IF NOT EXISTS uq_treatments_kind_name_plasmid
  ON public.treatments (kind_code, name, COALESCE(plasmid_code,''));

WITH src AS (
  SELECT
    j.id,
    COALESCE(NULLIF(lower(j.treatment_type_norm),''), NULLIF(lower(j.treatment_type),''), 'other') AS kind_code,
    COALESCE(NULLIF(j.treatment_code_norm,''), NULLIF(j.treatment_code,''), COALESCE(NULLIF(j.treatment_name,''),'unknown')) AS name,
    CASE
      WHEN COALESCE(NULLIF(lower(j.treatment_type_norm),''), NULLIF(lower(j.treatment_type),'')) = 'plasmid'
      THEN COALESCE(NULLIF(j.treatment_code_norm,''), NULLIF(j.treatment_code,''))
      ELSE NULL
    END AS plasmid_code
  FROM public.join_clutch_treatments j
)
INSERT INTO public.treatments (kind_code, name, plasmid_code)
SELECT DISTINCT s.kind_code, s.name, s.plasmid_code
FROM src s
LEFT JOIN public.treatments t
  ON t.kind_code=s.kind_code
 AND t.name=s.name
 AND COALESCE(t.plasmid_code,'')=COALESCE(s.plasmid_code,'')
WHERE t.id IS NULL;

WITH src AS (
  SELECT
    j.id,
    COALESCE(NULLIF(lower(j.treatment_type_norm),''), NULLIF(lower(j.treatment_type),''), 'other') AS kind_code,
    COALESCE(NULLIF(j.treatment_code_norm,''), NULLIF(j.treatment_code,''), COALESCE(NULLIF(j.treatment_name,''),'unknown')) AS name,
    CASE
      WHEN COALESCE(NULLIF(lower(j.treatment_type_norm),''), NULLIF(lower(j.treatment_type),'')) = 'plasmid'
      THEN COALESCE(NULLIF(j.treatment_code_norm,''), NULLIF(j.treatment_code,''))
      ELSE NULL
    END AS plasmid_code
  FROM public.join_clutch_treatments j
)
UPDATE public.join_clutch_treatments j
SET treatment_id = t.id
FROM src s
JOIN public.treatments t
  ON t.kind_code=s.kind_code
 AND t.name=s.name
 AND COALESCE(t.plasmid_code,'')=COALESCE(s.plasmid_code,'')
WHERE j.id=s.id
  AND j.treatment_id IS NULL;

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
