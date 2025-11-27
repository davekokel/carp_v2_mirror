BEGIN;

ALTER TABLE public.fish_groups
  DROP COLUMN IF EXISTS nickname;

COMMIT;
