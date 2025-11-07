BEGIN;

ALTER TABLE public.fluors
  ADD COLUMN IF NOT EXISTS excitation_nm smallint,
  ADD COLUMN IF NOT EXISTS emission_nm  smallint,
  ADD COLUMN IF NOT EXISTS alt_names    text[];

ALTER TABLE public.dyes
  ADD COLUMN IF NOT EXISTS excitation_nm smallint,
  ADD COLUMN IF NOT EXISTS emission_nm  smallint,
  ADD COLUMN IF NOT EXISTS alt_names    text[];

CREATE INDEX IF NOT EXISTS idx_fluors_name_ci ON public.fluors (lower(fluor_name));
CREATE INDEX IF NOT EXISTS idx_dyes_name_ci   ON public.dyes   (lower(dye_name));

COMMIT;
