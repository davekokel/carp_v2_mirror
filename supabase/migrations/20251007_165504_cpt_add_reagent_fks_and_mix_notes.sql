BEGIN;

-- Link to reagents (optional FKs)
ALTER TABLE public.cross_plan_treatments
  ADD COLUMN IF NOT EXISTS rna_id      uuid NULL REFERENCES public.rna_registry(id) ON DELETE RESTRICT,
  ADD COLUMN IF NOT EXISTS plasmid_id  uuid NULL REFERENCES public.plasmid_registry(id) ON DELETE RESTRICT;

-- At most one of rna_id / plasmid_id set
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname = 'chk_cpt_one_reagent'
      AND conrelid = 'public.cross_plan_treatments'::regclass
  ) THEN
    ALTER TABLE public.cross_plan_treatments
      ADD CONSTRAINT chk_cpt_one_reagent
      CHECK ( ((rna_id IS NOT NULL)::int + (plasmid_id IS NOT NULL)::int) <= 1 );
  END IF;
END$$;

-- Treatment-specific details
ALTER TABLE public.cross_plan_treatments
  ADD COLUMN IF NOT EXISTS injection_mix   text NULL,
  ADD COLUMN IF NOT EXISTS treatment_notes text NULL;

-- Helpful indexes
CREATE INDEX IF NOT EXISTS idx_cpt_rna      ON public.cross_plan_treatments(rna_id);
CREATE INDEX IF NOT EXISTS idx_cpt_plasmid  ON public.cross_plan_treatments(plasmid_id);

COMMIT;
