BEGIN;

CREATE TEMP TABLE _map (
  clutch_code text,
  treat_code text,
  treat_text text,
  n_rois text,
  treatment_infer_source text,
  treatment_infer_rule text,
  treatment_infer_batch_id text
);

\copy _map from 'seed_kits/legacy_wrangling_v4/working/clutch_treatment_mapping_from_v4__ideal.dbclutchcode.csv' with (format csv, header true);

INSERT INTO public.treatments (id, treat_code, kind_code, treat_text, notes, source_system, import_batch_id, created_at)
SELECT
  gen_random_uuid(),
  m.treat_code,
  'legacy',
  NULLIF(btrim(m.treat_text),''),
  '',
  'legacy_imaging',
  COALESCE(NULLIF(btrim(m.treatment_infer_batch_id),''), 'legacy_wrangling_v4_ideal'),
  now()
FROM (
  SELECT DISTINCT treat_code, treat_text, treatment_infer_batch_id
  FROM _map
  WHERE COALESCE(btrim(treat_code),'') <> ''
) m
LEFT JOIN public.treatments t ON t.treat_code = m.treat_code
WHERE t.id IS NULL;

COMMIT;

SELECT
  count(*) filter (where treat_code like 'T-EXP-%')    as n_exp,
  count(*) filter (where treat_code like 'T-LEGACY-%') as n_legacy,
  count(*) as n_total
FROM public.treatments;
