BEGIN;

ALTER TABLE public.join_fish_fluorescent_treatments
  ADD COLUMN IF NOT EXISTS created_at timestamptz DEFAULT now() NOT NULL;

DO $$
DECLARE fish_pk text;
BEGIN
  SELECT column_name INTO fish_pk
  FROM information_schema.columns
  WHERE table_schema='public' AND table_name='fish'
    AND column_name IN ('id','fish_uuid')
  ORDER BY CASE column_name WHEN 'id' THEN 1 WHEN 'fish_uuid' THEN 2 ELSE 9 END
  LIMIT 1;

  IF fish_pk IS NULL THEN
    RAISE EXCEPTION 'fish primary key column not found (expected id or fish_uuid)';
  END IF;

  IF EXISTS (
    SELECT 1
    FROM information_schema.table_constraints
    WHERE table_schema='public' AND table_name='join_fish_fluorescent_treatments'
      AND constraint_name='fk_jfft_fish'
  ) THEN
    EXECUTE 'ALTER TABLE public.join_fish_fluorescent_treatments DROP CONSTRAINT fk_jfft_fish';
  END IF;

  EXECUTE format(
    'ALTER TABLE public.join_fish_fluorescent_treatments
       ADD CONSTRAINT fk_jfft_fish
       FOREIGN KEY (fish_id) REFERENCES public.fish(%I) ON DELETE CASCADE',
    fish_pk
  );
END$$;

ALTER TABLE public.join_fish_fluorescent_treatments
  DROP CONSTRAINT IF EXISTS fk_jfft_ft;
ALTER TABLE public.join_fish_fluorescent_treatments
  ADD CONSTRAINT fk_jfft_ft
  FOREIGN KEY (ft_code) REFERENCES public.fluorescent_treatments(ft_code) ON DELETE CASCADE;

DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='join_fish_fluorescent_treatments'
      AND column_name='zygosity'
  ) THEN
    ALTER TABLE public.join_fish_fluorescent_treatments
      DROP CONSTRAINT IF EXISTS ck_jfft_zygosity;
    ALTER TABLE public.join_fish_fluorescent_treatments
      ADD CONSTRAINT ck_jfft_zygosity
      CHECK (zygosity IN ('het','hom','unk') OR zygosity IS NULL);
  END IF;
END$$;

DROP INDEX IF EXISTS uq_jfft_fish_ft;
CREATE UNIQUE INDEX uq_jfft_fish_ft
  ON public.join_fish_fluorescent_treatments(fish_id, ft_code);

COMMIT;
