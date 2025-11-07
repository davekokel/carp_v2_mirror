BEGIN;
CREATE TABLE IF NOT EXISTS public.ft_dyes (
  ft_code  text NOT NULL REFERENCES public.treatments_fluorescent(ft_code) ON DELETE CASCADE,
  dye_code text NOT NULL REFERENCES public.dyes(dye_code)                  ON DELETE CASCADE,
  PRIMARY KEY (ft_code, dye_code)
);
COMMIT;
