BEGIN;

ALTER TABLE public.fish
  ADD COLUMN IF NOT EXISTS fish_name           text,
  ADD COLUMN IF NOT EXISTS fish_nickname       text,
  ADD COLUMN IF NOT EXISTS genetic_background  text,
  ADD COLUMN IF NOT EXISTS line_building_stage text,
  ADD COLUMN IF NOT EXISTS date_birth          date;

-- v_fish_rich is defined by later canonical migrations; no-op here to avoid column rename conflicts
DO $$ BEGIN NULL; END $$;

COMMIT;
