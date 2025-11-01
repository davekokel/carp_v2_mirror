BEGIN;
CREATE UNIQUE INDEX IF NOT EXISTS uq_jpf_plasmid_fusion
  ON public.join_plasmid_fusions(plasmid_code, fusion_code);
COMMIT;
