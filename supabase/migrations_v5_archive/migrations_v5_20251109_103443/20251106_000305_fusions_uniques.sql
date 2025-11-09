BEGIN;
-- One tag+fluor combo only
CREATE UNIQUE INDEX IF NOT EXISTS uq_fusions_tag_fluor
  ON public.fusions (tag_id, fluor_id)
  WHERE tag_id IS NOT NULL AND fluor_id IS NOT NULL;

-- Only one fluor-only fusion per fluor
CREATE UNIQUE INDEX IF NOT EXISTS uq_fusions_fluor_only
  ON public.fusions (fluor_id)
  WHERE tag_id IS NULL AND fluor_id IS NOT NULL;

-- Only one tag-only fusion per tag
CREATE UNIQUE INDEX IF NOT EXISTS uq_fusions_tag_only
  ON public.fusions (tag_id)
  WHERE fluor_id IS NULL AND tag_id IS NOT NULL;
COMMIT;
