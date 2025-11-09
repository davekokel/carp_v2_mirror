BEGIN;
ALTER TABLE public.fluors ADD COLUMN IF NOT EXISTS excitation_nm integer;
ALTER TABLE public.fluors ADD COLUMN IF NOT EXISTS emission_nm   integer;
-- store many alternate names cleanly
ALTER TABLE public.fluors ADD COLUMN IF NOT EXISTS alt_names     text[];
ALTER TABLE public.fluors ADD COLUMN IF NOT EXISTS notes         text;
COMMIT;
