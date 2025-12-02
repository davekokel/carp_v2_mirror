BEGIN;

-- v11: add instance-level genetic_background (front-fill only).

ALTER TABLE public.fish_instances_v10
  ADD COLUMN IF NOT EXISTS genetic_background text;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'fk_fish_instances_bg_instance_level'
  ) THEN
    ALTER TABLE public.fish_instances_v10
      ADD CONSTRAINT fk_fish_instances_bg_instance_level
      FOREIGN KEY (genetic_background)
      REFERENCES public.genetic_backgrounds(bg_code)
      ON UPDATE CASCADE
      ON DELETE RESTRICT;
  END IF;
END$$;

COMMIT;
