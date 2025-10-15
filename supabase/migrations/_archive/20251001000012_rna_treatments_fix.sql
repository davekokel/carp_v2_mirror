-- migrations/2025-10-01_rna_treatments_fix.sql

-- 1) Ensure at_time exists (idempotent)
ALTER TABLE public.injected_rna_treatments
  ADD COLUMN IF NOT EXISTS at_time timestamptz;

-- 2) Ensure fish_id exists (idempotent)
ALTER TABLE public.injected_rna_treatments
  ADD COLUMN IF NOT EXISTS fish_id uuid;

-- 3) Add FK on fish_id (idempotent);
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint c
    WHERE c.conname = 'irt_fish_fk'
      AND c.conrelid = 'public.injected_rna_treatments'::regclass
  ) THEN
    ALTER TABLE public.injected_rna_treatments
      ADD CONSTRAINT irt_fish_fk
      FOREIGN KEY (fish_id) REFERENCES public.fish(id)
      ON DELETE CASCADE;
  END IF;
END $$;

-- 4) Helpful index by rna_id
CREATE INDEX IF NOT EXISTS ix_injected_rna_treatments_rna
  ON public.injected_rna_treatments (rna_id);

-- 5) Natural-key uniqueness for de-duping loader inserts
CREATE UNIQUE INDEX IF NOT EXISTS uq_irt_natural
  ON public.injected_rna_treatments (fish_id, rna_id, at_time, amount, units, note);
