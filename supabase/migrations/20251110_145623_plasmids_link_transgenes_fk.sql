BEGIN;
INSERT INTO public.transgenes (transgene_base_code, name, created_at)
SELECT p.code, NULL, now()
FROM public.plasmids p
LEFT JOIN public.transgenes t ON t.transgene_base_code = p.code
WHERE t.transgene_base_code IS NULL;
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE schemaname='public' AND indexname='uq_transgenes_base_code') THEN
    CREATE UNIQUE INDEX uq_transgenes_base_code ON public.transgenes(transgene_base_code);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE schemaname='public' AND indexname='uq_plasmids_code') THEN
    CREATE UNIQUE INDEX uq_plasmids_code ON public.plasmids(code);
  END IF;
END$$;
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='fk_plasmids_transgene_base') THEN
    ALTER TABLE public.plasmids
      ADD CONSTRAINT fk_plasmids_transgene_base
      FOREIGN KEY (code)
      REFERENCES public.transgenes(transgene_base_code)
      ON UPDATE CASCADE ON DELETE RESTRICT NOT VALID;
    ALTER TABLE public.plasmids VALIDATE CONSTRAINT fk_plasmids_transgene_base;
  END IF;
END$$;
COMMIT;
