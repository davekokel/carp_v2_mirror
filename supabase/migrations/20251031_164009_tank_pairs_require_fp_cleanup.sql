DO $$
DECLARE
  rec RECORD;
BEGIN
  -- 1) Drop any trigger ON tank_pairs whose function name or body hints at "require fp"
  FOR rec IN
    SELECT t.tgname, (p.oid::regprocedure)::text AS regproc
    FROM pg_trigger t
    JOIN pg_class c ON c.oid=t.tgrelid
    JOIN pg_namespace n ON n.oid=c.relnamespace
    JOIN pg_proc p ON p.oid=t.tgfoid
    WHERE NOT t.tgisinternal
      AND n.nspname='public' AND c.relname='tank_pairs'
      AND (
        p.proname ILIKE '%require%fp%' OR
        p.proname ILIKE '%tank_pairs%fp%' OR
        pg_get_functiondef(p.oid) ILIKE '%fish_pair_code%' OR
        pg_get_functiondef(p.oid) ILIKE '%must not be NULL%'
      )
  LOOP
    EXECUTE format('DROP TRIGGER IF EXISTS %I ON public.tank_pairs', rec.tgname);
  END LOOP;

  -- 2) Drop the trigger functions by exact signature (regprocedure) if any remain
  FOR rec IN
    SELECT DISTINCT (p.oid::regprocedure)::text AS regproc
    FROM pg_proc p
    WHERE pg_get_functiondef(p.oid) ILIKE '%fish_pair_code%' OR
          pg_get_functiondef(p.oid) ILIKE '%must not be NULL%' OR
          p.proname ILIKE '%require%fp%'
  LOOP
    EXECUTE format('DROP FUNCTION IF EXISTS %s CASCADE', rec.regproc);
  END LOOP;

  -- 3) Make fish_pair_code nullable if it was NOT NULL
  IF EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_schema='public' AND table_name='tank_pairs'
      AND column_name='fish_pair_code' AND is_nullable='NO'
  ) THEN
    EXECUTE 'ALTER TABLE public.tank_pairs ALTER COLUMN fish_pair_code DROP NOT NULL';
  END IF;

  -- 4) Add uniqueness guard for physical pairing (handle either column naming pattern)
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
