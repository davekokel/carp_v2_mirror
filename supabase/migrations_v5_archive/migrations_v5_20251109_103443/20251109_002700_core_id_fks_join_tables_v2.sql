BEGIN;

DO $$
BEGIN
  IF to_regclass('public.join_fish_transgene_alleles') IS NOT NULL THEN
    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE schemaname='public' AND tablename='join_fish_transgene_alleles' AND indexname='idx_jfta_fish_id') THEN
      EXECUTE 'CREATE INDEX idx_jfta_fish_id ON public.join_fish_transgene_alleles(fish_id)';
    END IF;
    IF NOT EXISTS (
      SELECT 1 FROM pg_constraint
      WHERE conname='fk_jfta_fish_id__fish_id'
        AND conrelid='public.join_fish_transgene_alleles'::regclass
    ) THEN
      ALTER TABLE public.join_fish_transgene_alleles
        ADD CONSTRAINT fk_jfta_fish_id__fish_id
        FOREIGN KEY (fish_id) REFERENCES public.fish(id)
        ON DELETE RESTRICT ON UPDATE RESTRICT
        DEFERRABLE INITIALLY DEFERRED
        NOT VALID;
    END IF;
  END IF;
END$$;

DO $$
BEGIN
  IF to_regclass('public.fish_tank_memberships') IS NOT NULL THEN
    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE schemaname='public' AND tablename='fish_tank_memberships' AND indexname='idx_ftm_fish_id') THEN
      EXECUTE 'CREATE INDEX idx_ftm_fish_id ON public.fish_tank_memberships(fish_id)';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE schemaname='public' AND tablename='fish_tank_memberships' AND indexname='idx_ftm_tank_id') THEN
      EXECUTE 'CREATE INDEX idx_ftm_tank_id ON public.fish_tank_memberships(tank_id)';
    END IF;
    IF NOT EXISTS (
      SELECT 1 FROM pg_constraint
      WHERE conname='fk_ftm_fish_id__fish_id'
        AND conrelid='public.fish_tank_memberships'::regclass
    ) THEN
      ALTER TABLE public.fish_tank_memberships
        ADD CONSTRAINT fk_ftm_fish_id__fish_id
        FOREIGN KEY (fish_id) REFERENCES public.fish(id)
        ON DELETE RESTRICT ON UPDATE RESTRICT
        DEFERRABLE INITIALLY DEFERRED
        NOT VALID;
    END IF;
    IF NOT EXISTS (
      SELECT 1 FROM pg_constraint
      WHERE conname='fk_ftm_tank_id__tanks_id'
        AND conrelid='public.fish_tank_memberships'::regclass
    ) THEN
      ALTER TABLE public.fish_tank_memberships
        ADD CONSTRAINT fk_ftm_tank_id__tanks_id
        FOREIGN KEY (tank_id) REFERENCES public.tanks(id)
        ON DELETE RESTRICT ON UPDATE RESTRICT
        DEFERRABLE INITIALLY DEFERRED
        NOT VALID;
    END IF;
  END IF;
END$$;

COMMIT;
