BEGIN;

-- Add FK as NOT VALID (only if missing), then validate if no orphans
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conrelid='public.treatments'::regclass
      AND conname='fk_treatments_plasmid_code'
  ) THEN
    ALTER TABLE public.treatments
    ADD CONSTRAINT fk_treatments_plasmid_code
    FOREIGN KEY (plasmid_code) REFERENCES public.plasmids(code)
    ON UPDATE CASCADE ON DELETE SET NULL
    NOT VALID;
  END IF;
END$$;

-- Validate if everything matches
DO $$
DECLARE n int;
BEGIN
  SELECT count(*) INTO n
  FROM public.treatments t
  LEFT JOIN public.plasmids p ON p.code = t.plasmid_code
  WHERE t.plasmid_code IS NOT NULL
    AND p.code IS NULL;

  IF n = 0 THEN
    BEGIN
      ALTER TABLE public.treatments VALIDATE CONSTRAINT fk_treatments_plasmid_code;
    EXCEPTION WHEN undefined_object THEN
      NULL;
    END;
  ELSE
    RAISE NOTICE 'Skipped VALIDATE fk_treatments_plasmid_code (% orphan rows).', n;
  END IF;
END$$;

-- Helpful lookup index
CREATE INDEX IF NOT EXISTS idx_treatments_plasmid_code ON public.treatments(plasmid_code);

COMMIT;
