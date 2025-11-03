BEGIN;

CREATE EXTENSION IF NOT EXISTS btree_gist;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='join_fish_tanks' AND column_name='valid_from')
  THEN EXECUTE 'ALTER TABLE public.join_fish_tanks ADD COLUMN valid_from timestamptz'; END IF;

  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='join_fish_tanks' AND column_name='valid_to')
  THEN EXECUTE 'ALTER TABLE public.join_fish_tanks ADD COLUMN valid_to timestamptz'; END IF;
END$$;

DO $$
DECLARE
  src_from text;
  src_to   text;
BEGIN
  SELECT col INTO src_from FROM (
    SELECT 'since'::text AS col WHERE EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='join_fish_tanks' AND column_name='since')
    UNION ALL SELECT 'created_at'::text AS col WHERE EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='join_fish_tanks' AND column_name='created_at')
  ) s LIMIT 1;

  SELECT col INTO src_to FROM (
    SELECT 'until'::text AS col WHERE EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='join_fish_tanks' AND column_name='until')
  ) s LIMIT 1;

  IF src_from IS NULL THEN
    EXECUTE 'UPDATE public.join_fish_tanks SET valid_from = COALESCE(valid_from, now()) WHERE valid_from IS NULL';
  ELSE
    EXECUTE format('UPDATE public.join_fish_tanks SET valid_from = COALESCE(valid_from, %I, now()) WHERE valid_from IS NULL', src_from);
  END IF;

  IF src_to IS NOT NULL THEN
    EXECUTE format('UPDATE public.join_fish_tanks SET valid_to = COALESCE(valid_to, %I) WHERE valid_to IS NULL', src_to);
  END IF;
END$$;

DO $$
BEGIN
  ALTER TABLE public.join_fish_tanks ALTER COLUMN valid_from SET NOT NULL;
EXCEPTION WHEN others THEN NULL;
END$$;

CREATE UNIQUE INDEX IF NOT EXISTS uq_jft_one_open_per_fish
  ON public.join_fish_tanks(fish_id)
  WHERE valid_to IS NULL;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conrelid = 'public.join_fish_tanks'::regclass
      AND conname  = 'ex_jft_no_overlap'
  ) THEN
    EXECUTE $sql$
      ALTER TABLE public.join_fish_tanks
      ADD CONSTRAINT ex_jft_no_overlap
      EXCLUDE USING gist (
        fish_id WITH =,
        tstzrange(valid_from, COALESCE(valid_to, 'infinity'::timestamptz), '[)') WITH &&
      )
    $sql$;
  END IF;
END$$;

COMMIT;
