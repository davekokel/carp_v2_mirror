BEGIN;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname='fk_jpf_plasmid_code' AND conrelid='public.join_plasmid_fusions'::regclass
  ) THEN
    ALTER TABLE public.join_plasmid_fusions
    ADD CONSTRAINT fk_jpf_plasmid_code
    FOREIGN KEY (plasmid_code) REFERENCES public.plasmids(code) ON UPDATE CASCADE ON DELETE RESTRICT NOT VALID;
  END IF;
END$$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname='fk_jpf_fusion_code' AND conrelid='public.join_plasmid_fusions'::regclass
  ) THEN
    ALTER TABLE public.join_plasmid_fusions
    ADD CONSTRAINT fk_jpf_fusion_code
    FOREIGN KEY (fusion_code) REFERENCES public.fusions(fusion_code) ON UPDATE CASCADE ON DELETE RESTRICT NOT VALID;
  END IF;
END$$;

CREATE OR REPLACE VIEW public.v_plasmid_fusions_pretty AS
SELECT
  j.id::text          AS join_id,
  p.id::text          AS plasmid_id,
  p.code              AS plasmid_code,
  p.name              AS plasmid_name,
  f.fusion_code,
  f.fusion_name,
  j.position,
  j.created_at
FROM public.join_plasmid_fusions j
JOIN public.plasmids p     ON p.code=j.plasmid_code
JOIN public.fusions  f     ON f.fusion_code=j.fusion_code
ORDER BY p.code, j.position NULLS LAST;

COMMIT;
