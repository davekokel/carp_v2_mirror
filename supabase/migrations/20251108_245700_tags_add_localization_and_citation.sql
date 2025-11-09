BEGIN;

ALTER TABLE public.tags
  ADD COLUMN IF NOT EXISTS localization   text,
  ADD COLUMN IF NOT EXISTS citation_link  text;

COMMIT;
