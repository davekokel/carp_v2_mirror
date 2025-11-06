BEGIN;
CREATE UNIQUE INDEX IF NOT EXISTS uq_join_plasmid_fusions_ids
  ON public.join_plasmid_fusions(plasmid_id, fusion_id);
COMMIT;
