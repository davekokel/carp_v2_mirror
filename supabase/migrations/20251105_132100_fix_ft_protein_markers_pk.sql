BEGIN;

DROP TABLE IF EXISTS public.ft_protein_markers;

CREATE TABLE public.ft_protein_markers (
  id        bigserial PRIMARY KEY,
  ft_code   text NOT NULL REFERENCES public.fluorescent_treatments(ft_code) ON DELETE CASCADE,
  fluor_code text NOT NULL REFERENCES public.fluors(fluor_code),
  tag_code   text REFERENCES public.tags(tag_code)
);

CREATE UNIQUE INDEX uq_ft_protein_marker
  ON public.ft_protein_markers (ft_code, COALESCE(tag_code,'∅'), fluor_code);

COMMIT;
