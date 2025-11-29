BEGIN;

-- 1) Temp table for the mapping
DROP TABLE IF EXISTS tmp_clutch_treatments_mapping;
CREATE TEMP TABLE tmp_clutch_treatments_mapping (
  clutch_code    text,
  treatment_code text
);

-- 2) Load mapping CSV into temp table
\copy tmp_clutch_treatments_mapping (clutch_code, treatment_code)
  FROM 'seed_kits/legacy_wrangling_v2/working/clutch_treatment_mapping_v11.csv'
  CSV HEADER;

-- 3) Insert into join_clutch_treatments, skipping existing links
INSERT INTO public.join_clutch_treatments
  (id, clutch_id, treatment_id, applied_at, created_at, notes)
SELECT
  gen_random_uuid()      AS id,
  c.id                   AS clutch_id,
  t.id                   AS treatment_id,
  now()                  AS applied_at,
  now()                  AS created_at,
  'legacy_v9/v10_mapping_csv' AS notes
FROM tmp_clutch_treatments_mapping m
JOIN public.clutches   c ON c.clutch_code = m.clutch_code
JOIN public.treatments t ON t.treat_code  = m.treatment_code
LEFT JOIN public.join_clutch_treatments j
  ON j.clutch_id    = c.id
 AND j.treatment_id = t.id
WHERE j.id IS NULL;

COMMIT;
