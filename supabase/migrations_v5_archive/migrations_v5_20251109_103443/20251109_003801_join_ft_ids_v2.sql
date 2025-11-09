BEGIN;
CREATE TABLE IF NOT EXISTS public.join_ft_dyes (
  ft_id uuid NOT NULL,
  dye_id uuid NOT NULL,
  created_at timestamptz DEFAULT now(),
  PRIMARY KEY (ft_id, dye_id)
);
CREATE TABLE IF NOT EXISTS public.join_ft_fusions (
  ft_id uuid NOT NULL,
  fusion_id uuid NOT NULL,
  created_at timestamptz DEFAULT now(),
  PRIMARY KEY (ft_id, fusion_id)
);
CREATE INDEX IF NOT EXISTS idx_join_ft_dyes_ft_id ON public.join_ft_dyes(ft_id);
CREATE INDEX IF NOT EXISTS idx_join_ft_dyes_dye_id ON public.join_ft_dyes(dye_id);
CREATE INDEX IF NOT EXISTS idx_join_ft_fusions_ft_id ON public.join_ft_fusions(ft_id);
CREATE INDEX IF NOT EXISTS idx_join_ft_fusions_fus_id ON public.join_ft_fusions(fusion_id);
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='fk_join_ft_dyes_ft_id__treatments_fluorescent_id' AND conrelid='public.join_ft_dyes'::regclass) THEN
    ALTER TABLE public.join_ft_dyes
      ADD CONSTRAINT fk_join_ft_dyes_ft_id__treatments_fluorescent_id
      FOREIGN KEY (ft_id) REFERENCES public.treatments_fluorescent(id)
      DEFERRABLE INITIALLY DEFERRED NOT VALID;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='fk_join_ft_dyes_dye_id__dyes_id' AND conrelid='public.join_ft_dyes'::regclass) THEN
    ALTER TABLE public.join_ft_dyes
      ADD CONSTRAINT fk_join_ft_dyes_dye_id__dyes_id
      FOREIGN KEY (dye_id) REFERENCES public.dyes(id)
      DEFERRABLE INITIALLY DEFERRED NOT VALID;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='fk_join_ft_fusions_ft_id__treatments_fluorescent_id' AND conrelid='public.join_ft_fusions'::regclass) THEN
    ALTER TABLE public.join_ft_fusions
      ADD CONSTRAINT fk_join_ft_fusions_ft_id__treatments_fluorescent_id
      FOREIGN KEY (ft_id) REFERENCES public.treatments_fluorescent(id)
      DEFERRABLE INITIALLY DEFERRED NOT VALID;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='fk_join_ft_fusions_fusion_id__fusions_id' AND conrelid='public.join_ft_fusions'::regclass) THEN
    ALTER TABLE public.join_ft_fusions
      ADD CONSTRAINT fk_join_ft_fusions_fusion_id__fusions_id
      FOREIGN KEY (fusion_id) REFERENCES public.fusions(id)
      DEFERRABLE INITIALLY DEFERRED NOT VALID;
  END IF;
END$$;
CREATE UNIQUE INDEX IF NOT EXISTS uq_fusions_fluor_tag ON public.fusions(fluor_id, tag_id);
COMMIT;
