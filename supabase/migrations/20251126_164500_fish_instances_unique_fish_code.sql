BEGIN;

ALTER TABLE public.fish_instances_v10
  DROP CONSTRAINT IF EXISTS fish_instances_v10_fish_code_key;

CREATE UNIQUE INDEX IF NOT EXISTS uniq_fish_instances_fish_code
  ON public.fish_instances_v10 (fish_code);

COMMIT;
