BEGIN;

DO $$
BEGIN
  IF to_regclass('public.ft_injection_mix_elements') IS NULL
     AND to_regclass('public.ft_injection_mix_sources') IS NOT NULL THEN
    EXECUTE 'ALTER TABLE public.ft_injection_mix_sources RENAME TO ft_injection_mix_elements';
  END IF;
END$$;

DO $$
DECLARE ft_unique_exists bool;
BEGIN
  SELECT EXISTS (
    SELECT 1 FROM information_schema.table_constraints
    WHERE table_schema='public' AND table_name='fluorescent_treatments'
      AND constraint_type IN ('PRIMARY KEY','UNIQUE')
  ) INTO ft_unique_exists;

  IF NOT ft_unique_exists THEN
    BEGIN
      EXECUTE 'ALTER TABLE public.fluorescent_treatments ADD PRIMARY KEY (ft_code)';
    EXCEPTION WHEN duplicate_object THEN
      IF NOT EXISTS (
        SELECT 1 FROM pg_indexes
        WHERE schemaname='public' AND tablename='fluorescent_treatments'
          AND indexname='uq_fluorescent_treatments_ft_code'
      ) THEN
        EXECUTE 'CREATE UNIQUE INDEX uq_fluorescent_treatments_ft_code ON public.fluorescent_treatments(ft_code)';
      END IF;
    END;
  END IF;
END$$;

DO $$
BEGIN
  IF to_regclass('public.ft_injection_mixes') IS NULL THEN
    EXECUTE 'CREATE TABLE public.ft_injection_mixes (ft_code text PRIMARY KEY, created_at timestamptz NOT NULL DEFAULT now())';
  END IF;
END$$;

ALTER TABLE public.ft_injection_mixes
  DROP CONSTRAINT IF EXISTS fk_ftmix_ft;
ALTER TABLE public.ft_injection_mixes
  ADD  CONSTRAINT fk_ftmix_ft
  FOREIGN KEY (ft_code) REFERENCES public.fluorescent_treatments(ft_code) ON DELETE CASCADE;

DO $$
DECLARE mix_col text;
BEGIN
  SELECT column_name INTO mix_col
  FROM information_schema.columns
  WHERE table_schema='public' AND table_name='ft_injection_mix_elements'
    AND column_name IN ('mix_code','ft_code','injection_mix_code')
  ORDER BY CASE column_name
             WHEN 'mix_code' THEN 1
             WHEN 'ft_code' THEN 2
             WHEN 'injection_mix_code' THEN 3
             ELSE 9
           END
  LIMIT 1;

  IF mix_col IS NULL THEN
    RAISE EXCEPTION 'ft_injection_mix_elements needs a mix code column (mix_code/ft_code/injection_mix_code)';
  END IF;

  EXECUTE 'ALTER TABLE public.ft_injection_mix_elements DROP CONSTRAINT IF EXISTS fk_ftmixel_mix';
  EXECUTE format(
    'ALTER TABLE public.ft_injection_mix_elements
       ADD CONSTRAINT fk_ftmixel_mix
       FOREIGN KEY (%I) REFERENCES public.ft_injection_mixes(ft_code) ON DELETE CASCADE',
    mix_col
  );
END$$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_indexes
    WHERE schemaname='public' AND tablename='ft_injection_mixes'
      AND indexname='uq_ft_injection_mixes_ft_code'
  ) THEN
    EXECUTE 'CREATE UNIQUE INDEX uq_ft_injection_mixes_ft_code ON public.ft_injection_mixes(ft_code)';
  END IF;
END$$;

COMMIT;
