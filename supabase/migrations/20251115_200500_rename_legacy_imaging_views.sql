BEGIN;

-- Rename legacy imaging normalizer views to v_legacy_* so it’s obvious they’re glue
ALTER VIEW IF EXISTS public.v_imaging_parent_alleles
  RENAME TO v_legacy_imaging_parent_alleles;

ALTER VIEW IF EXISTS public.v_imaging_injected
  RENAME TO v_legacy_imaging_injected;

COMMIT;
