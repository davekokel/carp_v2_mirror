BEGIN;

-- Prevent case-variant duplicates in catalogs (future-proof)
CREATE UNIQUE INDEX IF NOT EXISTS uq_tags_name_lower
  ON public.tags (lower(tag_name))
  WHERE tag_name IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_fluors_name_lower
  ON public.fluors (lower(fluor_name))
  WHERE fluor_name IS NOT NULL;

-- Ensure link uniqueness (safe if already present)
CREATE UNIQUE INDEX IF NOT EXISTS uq_join_plasmid_fusions_ids
  ON public.join_plasmid_fusions (plasmid_id, fusion_id);

COMMIT;
