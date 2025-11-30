BEGIN;

ALTER TABLE public.fish_lines
  ADD COLUMN IF NOT EXISTS transgene_base_code text,
  ADD COLUMN IF NOT EXISTS allele_nickname text;

CREATE INDEX IF NOT EXISTS idx_fish_lines_transgene
  ON public.fish_lines(transgene_base_code);

CREATE INDEX IF NOT EXISTS idx_fish_lines_allele
  ON public.fish_lines(allele_nickname);

COMMIT;
