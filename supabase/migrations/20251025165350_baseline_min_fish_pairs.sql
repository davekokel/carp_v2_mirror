BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Minimal fish_pairs so later generators/ALTERs can run
CREATE TABLE IF NOT EXISTS public.fish_pairs (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  mom_fish_id  uuid NOT NULL,
  dad_fish_id  uuid NOT NULL,
  created_by   text,
  created_at   timestamptz NOT NULL DEFAULT now()
);

-- FKs (safe if already present)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname = 'fk_fish_pairs_mom_id' AND conrelid = 'public.fish_pairs'::regclass
  ) THEN
    ALTER TABLE public.fish_pairs
      ADD CONSTRAINT fk_fish_pairs_mom_id
      FOREIGN KEY (mom_fish_id) REFERENCES public.fish(id) ON DELETE RESTRICT;
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname = 'fk_fish_pairs_dad_id' AND conrelid = 'public.fish_pairs'::regclass
  ) THEN
    ALTER TABLE public.fish_pairs
      ADD CONSTRAINT fk_fish_pairs_dad_id
      FOREIGN KEY (dad_fish_id) REFERENCES public.fish(id) ON DELETE RESTRICT;
  END IF;
END$$;

-- Unordered pair uniqueness; app canonicalizes (least/greatest) before insert
CREATE UNIQUE INDEX IF NOT EXISTS ux_fish_pairs_mom_dad
  ON public.fish_pairs (mom_fish_id, dad_fish_id);

COMMIT;
