BEGIN;

CREATE TABLE IF NOT EXISTS public.join_rna_fusions (
  rna_id    uuid NOT NULL,
  fusion_id uuid NOT NULL,
  created_at timestamptz DEFAULT now(),
  PRIMARY KEY (rna_id, fusion_id)
);

CREATE INDEX IF NOT EXISTS idx_jrf_rna_id    ON public.join_rna_fusions(rna_id);
CREATE INDEX IF NOT EXISTS idx_jrf_fusion_id ON public.join_rna_fusions(fusion_id);

COMMIT;
