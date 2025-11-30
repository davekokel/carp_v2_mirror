BEGIN;

ALTER TABLE public.fish_lines
  ALTER COLUMN nickname DROP NOT NULL;

COMMIT;
