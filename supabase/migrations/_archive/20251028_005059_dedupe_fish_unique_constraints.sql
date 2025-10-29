-- Keep the canonical fish_code constraint; drop redundant ones if present.
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname='uq_fish_code') THEN
    ALTER TABLE public.fish DROP CONSTRAINT uq_fish_code;
  END IF;
  IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname='uq_fish_fish_code') THEN
    ALTER TABLE public.fish DROP CONSTRAINT uq_fish_fish_code;
  END IF;
END$$;
