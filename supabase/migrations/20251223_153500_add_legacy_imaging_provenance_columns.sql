BEGIN;

ALTER TABLE public.imaging_clutch_memberships
  ADD COLUMN IF NOT EXISTS clutch_link_source text,
  ADD COLUMN IF NOT EXISTS clutch_link_rule text,
  ADD COLUMN IF NOT EXISTS clutch_link_batch_id text,
  ADD COLUMN IF NOT EXISTS clutch_linked_at timestamptz NOT NULL DEFAULT now();

ALTER TABLE public.clutches
  ADD COLUMN IF NOT EXISTS genotype_infer_source text,
  ADD COLUMN IF NOT EXISTS genotype_infer_rule text,
  ADD COLUMN IF NOT EXISTS genotype_infer_batch_id text,
  ADD COLUMN IF NOT EXISTS genotype_inferred_at timestamptz;

ALTER TABLE public.join_clutch_treatments
  ADD COLUMN IF NOT EXISTS treatment_infer_source text,
  ADD COLUMN IF NOT EXISTS treatment_infer_rule text,
  ADD COLUMN IF NOT EXISTS treatment_infer_batch_id text,
  ADD COLUMN IF NOT EXISTS treatment_inferred_at timestamptz;

COMMIT;
