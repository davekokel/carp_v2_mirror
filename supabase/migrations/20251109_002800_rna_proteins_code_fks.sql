BEGIN;
CREATE INDEX IF NOT EXISTS idx_rna_proteins_rna_code  ON public.rna_proteins(rna_code);
CREATE INDEX IF NOT EXISTS idx_rna_proteins_fluor_code ON public.rna_proteins(fluor_code);
CREATE INDEX IF NOT EXISTS idx_rna_proteins_tag_code   ON public.rna_proteins(tag_code);

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname='fk_rna_proteins_rna_code__rnas'
      AND conrelid='public.rna_proteins'::regclass
  ) THEN
    ALTER TABLE public.rna_proteins
      ADD CONSTRAINT fk_rna_proteins_rna_code__rnas
      FOREIGN KEY (rna_code) REFERENCES public.rnas(rna_code)
      DEFERRABLE INITIALLY DEFERRED
      NOT VALID;
  END IF;
END$$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname='fk_rna_proteins_fluor_code__fluors'
      AND conrelid='public.rna_proteins'::regclass
  ) THEN
    ALTER TABLE public.rna_proteins
      ADD CONSTRAINT fk_rna_proteins_fluor_code__fluors
      FOREIGN KEY (fluor_code) REFERENCES public.fluors(fluor_code)
      DEFERRABLE INITIALLY DEFERRED
      NOT VALID;
  END IF;
END$$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname='fk_rna_proteins_tag_code__tags'
      AND conrelid='public.rna_proteins'::regclass
  ) THEN
    ALTER TABLE public.rna_proteins
      ADD CONSTRAINT fk_rna_proteins_tag_code__tags
      FOREIGN KEY (tag_code) REFERENCES public.tags(tag_code)
      DEFERRABLE INITIALLY DEFERRED
      NOT VALID;
  END IF;
END$$;

COMMIT;
