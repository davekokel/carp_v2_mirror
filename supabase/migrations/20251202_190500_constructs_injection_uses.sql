BEGIN;

ALTER TABLE public.constructs
  ADD COLUMN IF NOT EXISTS injection_use_plasmid boolean NOT NULL DEFAULT false,
  ADD COLUMN IF NOT EXISTS injection_use_rna      boolean NOT NULL DEFAULT false,
  ADD COLUMN IF NOT EXISTS injection_use_crispr  boolean NOT NULL DEFAULT false;

COMMENT ON COLUMN public.constructs.injection_use_plasmid IS
  'True if this construct is used as an injected plasmid (from constructs_plasmid.used_for_injection_plasmid).';

COMMENT ON COLUMN public.constructs.injection_use_rna IS
  'True if this construct is used as an injected RNA (from constructs_plasmid.used_for_injection_rna).';

COMMENT ON COLUMN public.constructs.injection_use_crispr IS
  'True if this construct is used for CRISPR injections (from constructs_plasmid.used_for_injection_crispr).';

COMMIT;
