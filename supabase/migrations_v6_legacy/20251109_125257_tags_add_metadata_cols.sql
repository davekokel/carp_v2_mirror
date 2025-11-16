BEGIN;
ALTER TABLE public.tags ADD COLUMN IF NOT EXISTS localization  text;
ALTER TABLE public.tags ADD COLUMN IF NOT EXISTS note          text;
ALTER TABLE public.tags ADD COLUMN IF NOT EXISTS citation_link text;
COMMIT;
