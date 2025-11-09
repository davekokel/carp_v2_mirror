BEGIN;

-- 1) Ensure join table for fish ↔ fluorescent treatments is ID-first
-- If the legacy table exists, add ft_id and drop ft_code; otherwise no-op.
DO $$
BEGIN
  IF to_regclass('public.join_fish_fluorescent_treatments') IS NOT NULL THEN
    -- Add ft_id if missing
    IF NOT EXISTS (
      SELECT 1 FROM information_schema.columns
      WHERE table_schema='public' AND table_name='join_fish_fluorescent_treatments' AND column_name='ft_id'
    ) THEN
      ALTER TABLE public.join_fish_fluorescent_treatments
        ADD COLUMN ft_id uuid;
    END IF;

    -- Support index + FKs (deferrable, not validated)
    IF NOT EXISTS (
      SELECT 1 FROM pg_indexes
      WHERE schemaname='public' AND tablename='join_fish_fluorescent_treatments' AND indexname='idx_jfft_ft_id'
    ) THEN
      CREATE INDEX idx_jfft_ft_id ON public.join_fish_fluorescent_treatments(ft_id);
    END IF;

    IF NOT EXISTS (
      SELECT 1 FROM pg_constraint
      WHERE conname='fk_jfft_ft_id__treatments_fluorescent_id'
        AND conrelid='public.join_fish_fluorescent_treatments'::regclass
    ) THEN
      ALTER TABLE public.join_fish_fluorescent_treatments
        ADD CONSTRAINT fk_jfft_ft_id__treatments_fluorescent_id
        FOREIGN KEY (ft_id) REFERENCES public.treatments_fluorescent(id)
        DEFERRABLE INITIALLY DEFERRED NOT VALID;
    END IF;

    -- Ensure fish FK too (if not already)
    IF NOT EXISTS (
      SELECT 1 FROM pg_constraint
      WHERE conname='fk_jfft_fish_id__fish_id'
        AND conrelid='public.join_fish_fluorescent_treatments'::regclass
    ) THEN
      ALTER TABLE public.join_fish_fluorescent_treatments
        ADD CONSTRAINT fk_jfft_fish_id__fish_id
        FOREIGN KEY (fish_id) REFERENCES public.fish(id)
        DEFERRABLE INITIALLY DEFERRED NOT VALID;
    END IF;

    -- DB is empty → we can safely drop the legacy ft_code column if present
    IF EXISTS (
      SELECT 1 FROM information_schema.columns
      WHERE table_schema='public' AND table_name='join_fish_fluorescent_treatments' AND column_name='ft_code'
    ) THEN
      ALTER TABLE public.join_fish_fluorescent_treatments DROP COLUMN ft_code;
    END IF;
  END IF;
END$$;

-- 2) Legacy code-join for dyes → remove it outright (pages will be updated to use join_ft_dyes)
DROP TABLE IF EXISTS public.join_dyes_fluorescent_treatments CASCADE;

-- 3) Dyes must not link to fusions. If a stray dye_id exists on fusions, drop it (and any FK).
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='fusions' AND column_name='dye_id'
  ) THEN
    -- Drop any FK that might reference dyes
    PERFORM 1 FROM pg_constraint
      WHERE conrelid='public.fusions'::regclass AND conname='fk_fusions_dye_id__dyes_id';
    IF FOUND THEN
      ALTER TABLE public.fusions DROP CONSTRAINT fk_fusions_dye_id__dyes_id;
    END IF;

    ALTER TABLE public.fusions DROP COLUMN dye_id;
  END IF;
END$$;

COMMIT;
