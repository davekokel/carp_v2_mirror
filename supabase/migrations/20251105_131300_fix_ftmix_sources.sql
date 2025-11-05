BEGIN;

-- ft_injection_mix_sources (keep if your file already had this)
DROP TABLE IF EXISTS public.ft_injection_mix_sources;
CREATE TABLE public.ft_injection_mix_sources (
  id          bigserial PRIMARY KEY,
  ft_code     text NOT NULL
              REFERENCES public.fluorescent_treatments(ft_code) ON DELETE CASCADE,
  source_kind text NOT NULL CHECK (source_kind IN
              ('plasmid','enzyme','oligo','pcr_product','mrna','grna','protocol','other')),
  ref_code    text,
  ref_text    text,
  qty         numeric,
  units       text,
  role        text,
  notes       jsonb,
  CONSTRAINT ck_ftmix_src_ref_present CHECK (ref_code IS NOT NULL OR ref_text IS NOT NULL)
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_ftmix_src
  ON public.ft_injection_mix_sources (ft_code, source_kind, COALESCE(ref_code,'∅'), COALESCE(ref_text,'∅'));

-- ft_protein_markers (fixed: surrogate PK + UNIQUE INDEX using COALESCE)
DROP TABLE IF EXISTS public.ft_protein_markers;
CREATE TABLE public.ft_protein_markers (
  id         bigserial PRIMARY KEY,
  ft_code    text NOT NULL REFERENCES public.fluorescent_treatments(ft_code) ON DELETE CASCADE,
  fluor_code text NOT NULL REFERENCES public.fluors(fluor_code),
  tag_code   text NULL     REFERENCES public.tags(tag_code)
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_ft_protein_marker
  ON public.ft_protein_markers (ft_code, COALESCE(tag_code,'∅'), fluor_code);

COMMIT;
