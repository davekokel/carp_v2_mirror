BEGIN;

-- Preserve the current mgco-* (and any other) base codes before we normalize them.
ALTER TABLE public.constructs
  ADD COLUMN IF NOT EXISTS legacy_base_code text;

UPDATE public.constructs
SET legacy_base_code = base_code
WHERE legacy_base_code IS NULL;

COMMENT ON COLUMN public.constructs.legacy_base_code IS
'Historical/base code as originally loaded (e.g. mgco-*) prior to v11 basecode normalization to plasmid/transgene codes (e.g. pdqm-5, pswin-1).';

COMMIT;
