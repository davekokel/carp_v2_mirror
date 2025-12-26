BEGIN;

CREATE TEMP TABLE _bad_treats (treatment_id uuid PRIMARY KEY) ON COMMIT DROP;
INSERT INTO _bad_treats (treatment_id)
SELECT t.id
FROM public.treatments t
JOIN public.treatment_mixes tm ON tm.treatment_id = t.id
LEFT JOIN public.treatment_mix_constructs tmc ON tmc.mix_id = tm.id
LEFT JOIN public.treatment_mix_dyes tmd       ON tmd.mix_id = tm.id
WHERE t.treat_code LIKE 'T-EXP-%'
GROUP BY t.id
HAVING count(DISTINCT tmc.id) = 0 AND count(DISTINCT tmd.id) = 0;

CREATE TEMP TABLE _bad_join (join_id uuid PRIMARY KEY) ON COMMIT DROP;
INSERT INTO _bad_join (join_id)
SELECT j.id
FROM public.join_clutch_treatments j
JOIN _bad_treats bt ON bt.treatment_id = j.treatment_id
WHERE j.treatment_infer_source = 'exp_treatment_signatures_csv'
  AND j.treatment_infer_rule   = 'dataset_key+signature';

-- Unlink memberships that point at treated_clutches for these treatments
UPDATE public.imaging_clutch_memberships m
SET treated_clutch_id = NULL
WHERE m.treated_clutch_id IN (
  SELECT tc.id
  FROM public.treated_clutches_v11 tc
  JOIN _bad_treats bt ON bt.treatment_id = tc.treatment_id
);

-- Delete treated clutches for these treatments
DELETE FROM public.treated_clutches_v11 tc
WHERE tc.treatment_id IN (SELECT treatment_id FROM _bad_treats);

-- Delete join rows we own (from exp_treatment_signatures_csv / dataset_key+signature)
DELETE FROM public.join_clutch_treatments j
WHERE j.id IN (SELECT join_id FROM _bad_join);

-- Drop mixes and treatments (safe because we verified no remaining refs earlier; we’ll re-verify after)
DELETE FROM public.treatment_mixes tm
WHERE tm.treatment_id IN (SELECT treatment_id FROM _bad_treats);

DELETE FROM public.treatments t
WHERE t.id IN (SELECT treatment_id FROM _bad_treats);

COMMIT;
