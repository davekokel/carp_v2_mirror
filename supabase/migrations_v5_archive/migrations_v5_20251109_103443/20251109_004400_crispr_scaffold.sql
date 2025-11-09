BEGIN;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS public.crispr_knockins (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  knockin_code text UNIQUE NOT NULL,
  description text,
  created_at timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.join_crispr_fusions (
  knockin_id uuid NOT NULL,
  fusion_id  uuid NOT NULL,
  created_at timestamptz DEFAULT now(),
  PRIMARY KEY (knockin_id, fusion_id)
);

CREATE INDEX IF NOT EXISTS idx_jcf_knockin_id ON public.join_crispr_fusions(knockin_id);
CREATE INDEX IF NOT EXISTS idx_jcf_fusion_id  ON public.join_crispr_fusions(fusion_id);

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname='fk_jcf_knockin_id__crispr_knockins_id'
      AND conrelid='public.join_crispr_fusions'::regclass
  ) THEN
    ALTER TABLE public.join_crispr_fusions
      ADD CONSTRAINT fk_jcf_knockin_id__crispr_knockins_id
      FOREIGN KEY (knockin_id) REFERENCES public.crispr_knockins(id)
      DEFERRABLE INITIALLY DEFERRED NOT VALID;
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname='fk_jcf_fusion_id__fusions_id'
      AND conrelid='public.join_crispr_fusions'::regclass
  ) THEN
    ALTER TABLE public.join_crispr_fusions
      ADD CONSTRAINT fk_jcf_fusion_id__fusions_id
      FOREIGN KEY (fusion_id) REFERENCES public.fusions(id)
      DEFERRABLE INITIALLY DEFERRED NOT VALID;
  END IF;
END$$;

COMMIT;
