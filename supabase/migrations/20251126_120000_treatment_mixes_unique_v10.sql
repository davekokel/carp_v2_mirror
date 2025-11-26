BEGIN;

-- Ensure v10 treatment_mixes supports ON CONFLICT (treatment_id, mix_code)
-- used by scripts/v10_load_treatments_from_csv.py.

ALTER TABLE public.treatment_mixes
ADD CONSTRAINT uq_treatment_mixes_treatment_id_mix_code
UNIQUE (treatment_id, mix_code);

COMMIT;
