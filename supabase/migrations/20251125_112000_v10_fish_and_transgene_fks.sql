BEGIN;

-- 1) Wire fish_lines.genetic_background → genetic_backgrounds.bg_code
ALTER TABLE public.fish_lines
  ADD CONSTRAINT fk_fish_lines_bg
  FOREIGN KEY (genetic_background)
  REFERENCES public.genetic_backgrounds(bg_code)
  ON UPDATE CASCADE
  ON DELETE RESTRICT;

-- 2) Move tanks from legacy fish_id → v10 fish_instances_v10.id

-- Drop any existing foreign keys on public.tanks (e.g. fk_tanks_fish)
DO $$
DECLARE
  r record;
BEGIN
  FOR r IN
    SELECT conname
    FROM pg_constraint
    WHERE contype = 'f'
      AND conrelid = 'public.tanks'::regclass
  LOOP
    EXECUTE format('ALTER TABLE public.tanks DROP CONSTRAINT %I', r.conname);
  END LOOP;
END $$;

-- Rename fish_id → fish_instance_id (v10 cohort FK)
ALTER TABLE public.tanks
  RENAME COLUMN fish_id TO fish_instance_id;

-- Add FK to v10 fish_instances_v10
ALTER TABLE public.tanks
  ADD CONSTRAINT fk_tanks_fish_instance_v10
  FOREIGN KEY (fish_instance_id)
  REFERENCES public.fish_instances_v10(id)
  ON UPDATE CASCADE
  ON DELETE RESTRICT;

-- 3) Wire transgenes.transgene_base_code → constructs.construct_code
ALTER TABLE public.transgenes
  ADD CONSTRAINT fk_transgenes_construct
  FOREIGN KEY (transgene_base_code)
  REFERENCES public.constructs(construct_code)
  ON UPDATE CASCADE
  ON DELETE RESTRICT;

COMMIT;
