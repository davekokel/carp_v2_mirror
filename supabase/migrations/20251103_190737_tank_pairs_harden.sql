BEGIN;

-- PK on id (if missing)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conrelid='public.tank_pairs'::regclass AND contype='p'
  ) THEN
    ALTER TABLE public.tank_pairs
      ADD CONSTRAINT pk_tank_pairs PRIMARY KEY (id);
  END IF;
END$$;

-- FKs to tanks(id), guarded + NOT VALID first then validate if clean
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conrelid='public.tank_pairs'::regclass AND conname='fk_tank_pairs_mother'
  ) THEN
    ALTER TABLE public.tank_pairs
      ADD CONSTRAINT fk_tank_pairs_mother
      FOREIGN KEY (mother_tank_id) REFERENCES public.tanks(id)
      ON UPDATE CASCADE ON DELETE RESTRICT NOT VALID;
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conrelid='public.tank_pairs'::regclass AND conname='fk_tank_pairs_father'
  ) THEN
    ALTER TABLE public.tank_pairs
      ADD CONSTRAINT fk_tank_pairs_father
      FOREIGN KEY (father_tank_id) REFERENCES public.tanks(id)
      ON UPDATE CASCADE ON DELETE RESTRICT NOT VALID;
  END IF;
END$$;

-- Validate FKs if no orphans
DO $$
DECLARE n1 int; n2 int;
BEGIN
  SELECT count(*) INTO n1
  FROM public.tank_pairs tp LEFT JOIN public.tanks t ON t.id=tp.mother_tank_id
  WHERE t.id IS NULL;

  SELECT count(*) INTO n2
  FROM public.tank_pairs tp LEFT JOIN public.tanks t ON t.id=tp.father_tank_id
  WHERE t.id IS NULL;

  IF n1=0 THEN
    BEGIN ALTER TABLE public.tank_pairs VALIDATE CONSTRAINT fk_tank_pairs_mother; EXCEPTION WHEN undefined_object THEN NULL; END;
  ELSE RAISE NOTICE 'Skipped validate fk_tank_pairs_mother (% orphans)', n1; END IF;

  IF n2=0 THEN
    BEGIN ALTER TABLE public.tank_pairs VALIDATE CONSTRAINT fk_tank_pairs_father; EXCEPTION WHEN undefined_object THEN NULL; END;
  ELSE RAISE NOTICE 'Skipped validate fk_tank_pairs_father (% orphans)', n2; END IF;
END$$;

-- No self-pairing
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conrelid='public.tank_pairs'::regclass AND conname='ck_tank_pairs_not_self'
  ) THEN
    ALTER TABLE public.tank_pairs
      ADD CONSTRAINT ck_tank_pairs_not_self CHECK (mother_tank_id <> father_tank_id);
  END IF;
END$$;

-- Unique code
CREATE UNIQUE INDEX IF NOT EXISTS uq_tank_pairs_code
  ON public.tank_pairs (tank_pair_code);

-- Order-independent uniqueness of the pair
CREATE UNIQUE INDEX IF NOT EXISTS uq_tank_pairs_symmetry
  ON public.tank_pairs (
    LEAST(mother_tank_id, father_tank_id),
    GREATEST(mother_tank_id, father_tank_id)
  );

-- Helpful view with tank codes
COMMIT;
