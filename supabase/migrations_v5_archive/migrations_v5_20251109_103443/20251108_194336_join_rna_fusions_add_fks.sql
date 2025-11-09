BEGIN;

DO $$
BEGIN
  -- Add FKs only if referenced tables exist (guards for rebuilds)
  IF to_regclass('public.rnas') IS NOT NULL
     AND NOT EXISTS (
       SELECT 1 FROM pg_constraint
       WHERE conrelid='public.join_rna_fusions'::regclass
         AND conname='fk_jrf_rna_id__rnas_id'
     ) THEN
    ALTER TABLE public.join_rna_fusions
      ADD CONSTRAINT fk_jrf_rna_id__rnas_id
      FOREIGN KEY (rna_id) REFERENCES public.rnas(id)
      DEFERRABLE INITIALLY DEFERRED NOT VALID;
  END IF;

  IF to_regclass('public.fusions') IS NOT NULL
     AND NOT EXISTS (
       SELECT 1 FROM pg_constraint
       WHERE conrelid='public.join_rna_fusions'::regclass
         AND conname='fk_jrf_fusion_id__fusions_id'
     ) THEN
    ALTER TABLE public.join_rna_fusions
      ADD CONSTRAINT fk_jrf_fusion_id__fusions_id
      FOREIGN KEY (fusion_id) REFERENCES public.fusions(id)
      DEFERRABLE INITIALLY DEFERRED NOT VALID;
  END IF;
END$$;

COMMIT;
