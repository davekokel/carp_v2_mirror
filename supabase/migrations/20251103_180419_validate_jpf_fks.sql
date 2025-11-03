BEGIN;
ALTER TABLE public.join_plasmid_fusions VALIDATE CONSTRAINT fk_jpf_plasmid_code;
ALTER TABLE public.join_plasmid_fusions VALIDATE CONSTRAINT fk_jpf_fusion_code;
COMMIT;
