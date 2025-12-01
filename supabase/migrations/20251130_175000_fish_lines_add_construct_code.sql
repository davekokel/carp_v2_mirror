BEGIN;

ALTER TABLE public.fish_lines
  ADD COLUMN IF NOT EXISTS construct_code text;

COMMIT;
