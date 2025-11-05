BEGIN;

DROP VIEW IF EXISTS public.v_fish_fluorescent_markers;
DROP VIEW IF EXISTS public.v_fluorescent_treatment_markers;

DROP TABLE IF EXISTS public.ft_injection_mix_sources CASCADE;
CREATE TABLE public.ft_injection_mix_sources (
  mix_code   text    NOT NULL,
  source_key text    NOT NULL,
  source_val text    NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_ftmix_sources_mix ON public.ft_injection_mix_sources(mix_code);

DROP TABLE IF EXISTS public.ft_protein_markers CASCADE;
CREATE TABLE public.ft_protein_markers (
  id         uuid    PRIMARY KEY DEFAULT gen_random_uuid(),
  ft_code    text    NOT NULL,
  fluor_code text    NOT NULL,
  tag_code   text,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_ft_protein_marker
  ON public.ft_protein_markers(ft_code, COALESCE(tag_code,'∅'), fluor_code);
ALTER TABLE public.ft_protein_markers
  DROP CONSTRAINT IF EXISTS fk_ftpm_ft;
ALTER TABLE public.ft_protein_markers
  ADD  CONSTRAINT fk_ftpm_ft FOREIGN KEY (ft_code)
  REFERENCES public.fluorescent_treatments(ft_code) ON DELETE CASCADE;

DROP TABLE IF EXISTS public.ft_dye_markers CASCADE;
CREATE TABLE public.ft_dye_markers (
  id         uuid    PRIMARY KEY DEFAULT gen_random_uuid(),
  ft_code    text    NOT NULL,
  dye_code   text    NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_ft_dye_marker
  ON public.ft_dye_markers(ft_code, dye_code);
ALTER TABLE public.ft_dye_markers
  DROP CONSTRAINT IF EXISTS fk_ftdm_ft;
ALTER TABLE public.ft_dye_markers
  ADD  CONSTRAINT fk_ftdm_ft FOREIGN KEY (ft_code)
  REFERENCES public.fluorescent_treatments(ft_code) ON DELETE CASCADE;

COMMIT;
