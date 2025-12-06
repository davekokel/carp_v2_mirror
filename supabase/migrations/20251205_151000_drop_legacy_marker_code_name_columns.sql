BEGIN;

DROP VIEW IF EXISTS public.v11_dyes_star;

ALTER TABLE public.fluors
  DROP COLUMN IF EXISTS fluor_code,
  DROP COLUMN IF EXISTS fluor_name;

ALTER TABLE public.tags
  DROP COLUMN IF EXISTS tag_code,
  DROP COLUMN IF EXISTS tag_name;

ALTER TABLE public.dyes
  DROP COLUMN IF EXISTS dye_base_code,
  DROP COLUMN IF EXISTS name;

COMMIT;
