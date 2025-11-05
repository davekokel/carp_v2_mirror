BEGIN;

DROP VIEW IF EXISTS public.v_fish_fluorescent_markers;
DROP VIEW IF EXISTS public.v_fluorescent_treatment_markers;

DROP TABLE IF EXISTS public.ft_injection_mix_elements CASCADE;
CREATE TABLE public.ft_injection_mix_elements (
  mix_code   text    NOT NULL,
  source_key text    NOT NULL,
  source_val text    NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_ft_injection_mix_elements_key
  ON public.ft_injection_mix_elements(mix_code, source_key);

DROP TABLE IF EXISTS public.ft_proteins CASCADE;
CREATE TABLE public.ft_proteins (
  id         uuid    PRIMARY KEY DEFAULT gen_random_uuid(),
  ft_code    text    NOT NULL,
  fluor_code text    NOT NULL,
  tag_code   text,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_ft_proteins_marker
  ON public.ft_proteins(ft_code, COALESCE(tag_code,'∅'), fluor_code);

DROP TABLE IF EXISTS public.ft_dyes CASCADE;
CREATE TABLE public.ft_dyes (
  id         uuid    PRIMARY KEY DEFAULT gen_random_uuid(),
  ft_code    text    NOT NULL,
  dye_code   text    NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_ft_dyes_marker
  ON public.ft_dyes(ft_code, dye_code);

ALTER TABLE public.ft_proteins
  DROP CONSTRAINT IF EXISTS fk_ftproteins_ft;
ALTER TABLE public.ft_proteins
  ADD  CONSTRAINT fk_ftproteins_ft
  FOREIGN KEY (ft_code) REFERENCES public.fluorescent_treatments(ft_code) ON DELETE CASCADE;

ALTER TABLE public.ft_dyes
  DROP CONSTRAINT IF EXISTS fk_ftdyes_ft;
ALTER TABLE public.ft_dyes
  ADD  CONSTRAINT fk_ftdyes_ft
  FOREIGN KEY (ft_code) REFERENCES public.fluorescent_treatments(ft_code) ON DELETE CASCADE;

COMMIT;
