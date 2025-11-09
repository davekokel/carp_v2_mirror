BEGIN;
ALTER TABLE public.dyes DROP COLUMN IF EXISTS binds_tag_id;
ALTER TABLE public.dyes DROP COLUMN IF EXISTS localization;
COMMIT;
