BEGIN;

-- New symmetric join: rnas ↔ fusions
CREATE TABLE IF NOT EXISTS public.join_rna_fusions (
  rna_id    uuid NOT NULL,
  fusion_id uuid NOT NULL,
  created_at timestamptz DEFAULT now(),
  PRIMARY KEY (rna_id, fusion_id)
);

-- Indexes for FK lookups
CREATE INDEX IF NOT EXISTS idx_jrf_rna_id    ON public.join_rna_fusions(rna_id);
CREATE INDEX IF NOT EXISTS idx_jrf_fusion_id ON public.join_rna_fusions(fusion_id);

-- Real FKs (structure now; validate after clean seed)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname='fk_jrf_rna_id__rnas_id'
      AND conrelid='public.join_rna_fusions'::regclass
  ) THEN
    ALTER TABLE public.join_rna_fusions
      ADD CONSTRAINT fk_jrf_rna_id__rnas_id
      FOREIGN KEY (rna_id) REFERENCES public.rnas(id)
      DEFERRABLE INITIALLY DEFERRED NOT VALID;
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname='fk_jrf_fusion_id__fusions_id'
      AND conrelid='public.join_rna_fusions'::regclass
  ) THEN
    ALTER TABLE public.join_rna_fusions
      ADD CONSTRAINT fk_jrf_fusion_id__fusions_id
      FOREIGN KEY (fusion_id) REFERENCES public.fusions(id)
      DEFERRABLE INITIALLY DEFERRED NOT VALID;
  END IF;
END$$;

COMMIT;
