BEGIN;

-- Add an explicit origin classification to each fish instance.
-- This is filled by the v11 fish loaders, not by older v9/v10 code.
ALTER TABLE public.fish_instances_v10
  ADD COLUMN IF NOT EXISTS origin_kind text;

COMMENT ON COLUMN public.fish_instances_v10.origin_kind IS
  'Machine-readable classification of how this instance was created (e.g. background_only, transgenic_new_line, transgenic_existing_line).';

COMMIT;
