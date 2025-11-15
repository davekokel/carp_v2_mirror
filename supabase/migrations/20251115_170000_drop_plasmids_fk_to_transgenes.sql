BEGIN;

-- Drop the FK that forces plasmids.code -> transgenes.transgene_base_code
-- Conceptually, plasmids are primary and transgenes are derived, so this
-- constraint points in the wrong direction for our model.
ALTER TABLE public.plasmids
  DROP CONSTRAINT IF EXISTS fk_plasmids_transgene_base;

COMMIT;
