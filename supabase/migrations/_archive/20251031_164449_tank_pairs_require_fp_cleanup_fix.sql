DO $$
DECLARE
  r RECORD;
BEGIN
  -- 1) Find all non-internal triggers on public.tank_pairs whose function enforces fish_pair_code
  FOR r IN
    SELECT t.tgname,
           (p.oid::regprocedure)::text AS regproc
    FROM pg_trigger t
    JOIN pg_class c     ON c.oid = t.tgrelid
    JOIN pg_namespace n ON n.oid = c.relnamespace
    JOIN pg_proc p      ON p.oid = t.tgfoid
    WHERE NOT t.tgisinternal
      AND n.nspname = 'public'
      AND c.relname = 'tank_pairs'
      AND p.prokind = 'f'                 -- functions only (skip aggregates/procedures)
      AND (
        p.proname ILIKE '%require%fp%' OR
        pg_get_functiondef(p.oid) ILIKE '%fish_pair_code%' OR
        pg_get_functiondef(p.oid) ILIKE '%must not be NULL%'
      )
  LOOP
    -- Drop the trigger first
    EXECUTE format('DROP TRIGGER IF EXISTS %I ON public.tank_pairs', r.tgname);
    -- Then drop the trigger function (CASCADE to clear stray dependents)
    EXECUTE format('DROP FUNCTION IF EXISTS %s CASCADE', r.regproc);
  END LOOP;

  -- 2) Make fish_pair_code nullable if needed
  IF EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_schema='public' AND table_name='tank_pairs'
      AND column_name='fish_pair_code' AND is_nullable='NO'
  ) THEN
    EXECUTE 'ALTER TABLE public.tank_pairs ALTER COLUMN fish_pair_code DROP NOT NULL';
  END IF;

  -- 3) Add uniqueness guard for physical pairing (handle either column naming)
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='uq_tank_pairs_mom_dad_concept') THEN
    IF EXISTS (SELECT 1 FROM information_schema.columns
               WHERE table_schema='public' AND table_name='tank_pairs' AND column_name='mother_tank_id')
       AND EXISTS (SELECT 1 FROM information_schema.columns
               WHERE table_schema='public' AND table_name='tank_pairs' AND column_name='father_tank_id') THEN
      EXECUTE 'ALTER TABLE public.tank_pairs
               ADD CONSTRAINT uq_tank_pairs_mom_dad_concept
               UNIQUE (mother_tank_id, father_tank_id, concept_id)';
    ELSIF EXISTS (SELECT 1 FROM information_schema.columns
               WHERE table_schema='public' AND table_name='tank_pairs' AND column_name='tank_id_mother')
       AND EXISTS (SELECT 1 FROM information_schema.columns
               WHERE table_schema='public' AND table_name='tank_pairs' AND column_name='tank_id_father') THEN
      EXECUTE 'ALTER TABLE public.tank_pairs
               ADD CONSTRAINT uq_tank_pairs_mom_dad_concept
               UNIQUE (tank_id_mother, tank_id_father, concept_id)';
    END IF;
  END IF;
END $$;
