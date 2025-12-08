BEGIN;

ALTER TABLE public.treatment_mix_constructs
  ADD COLUMN IF NOT EXISTS delivery_form text;

ALTER TABLE public.treatment_mix_constructs
  DROP CONSTRAINT IF EXISTS treatment_mix_constructs_delivery_form_chk;

ALTER TABLE public.treatment_mix_constructs
  ADD CONSTRAINT treatment_mix_constructs_delivery_form_chk
  CHECK (
    delivery_form IS NULL
    OR delivery_form IN ('plasmid','rna','crispr')
  );

COMMENT ON COLUMN public.treatment_mix_constructs.delivery_form IS
'How this construct was delivered in this treatment mix: plasmid, rna, or crispr.';

COMMIT;
