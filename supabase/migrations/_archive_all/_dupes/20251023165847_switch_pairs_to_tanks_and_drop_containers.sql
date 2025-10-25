BEGIN;

-- 0) Sanity: ensure public.tanks exists
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema='public' AND table_name='tanks'
  ) THEN
    RAISE EXCEPTION 'Expected public.tanks (tank_id, tank_code, fish_code, ...) to exist.';
  END IF;
END$$;

-- 1) Drop any existing FKs on tank_pairs (mother_tank_id / father_tank_id)
DO $$
DECLARE r RECORD;
BEGIN
  FOR r IN
    SELECT conname
    FROM   pg_constraint c
    JOIN   pg_class      t ON t.oid = c.conrelid
    WHERE  t.relname='tank_pairs' AND c.contype='f'
  LOOP
    EXECUTE format('ALTER TABLE public.tank_pairs DROP CONSTRAINT IF EXISTS %I', r.conname);
  END LOOP;
END$$;

-- 2) Re-add FKs to public.tanks(tank_id)
ALTER TABLE public.tank_pairs
  ADD CONSTRAINT tank_pairs_mother_tank_fk
  FOREIGN KEY (mother_tank_id) REFERENCES public.tanks(tank_id)
  ON UPDATE CASCADE ON DELETE RESTRICT;

ALTER TABLE public.tank_pairs
  ADD CONSTRAINT tank_pairs_father_tank_fk
  FOREIGN KEY (father_tank_id) REFERENCES public.tanks(tank_id)
  ON UPDATE CASCADE ON DELETE RESTRICT;

-- 3) (Re)build a tanks-only v_tank_pairs (no containers, no fish_id join)
CREATE OR REPLACE VIEW public.v_tank_pairs AS
SELECT
  tp.id,
  tp.tank_pair_code,
  tp.status,
  tp.role_orientation,
  tp.concept_id,
  tp.fish_pair_id,
  tp.created_by,
  tp.created_at,
  tp.updated_at,

  -- mother side
  mt.tank_id   AS mother_tank_id,
  mt.tank_code AS mom_tank_code,
  mt.fish_code AS mom_fish_code,

  -- father side
  dt.tank_id   AS father_tank_id,
  dt.tank_code AS dad_tank_code,
  dt.fish_code AS dad_fish_code

FROM public.tank_pairs tp
LEFT JOIN public.tanks mt ON mt.tank_id = tp.mother_tank_id
LEFT JOIN public.tanks dt ON dt.tank_id = tp.father_tank_id
ORDER BY tp.created_at DESC NULLS LAST;

-- 4) Unique guard (as an index) to avoid duplicate pairings for the same context/orientation
--    Normalize NULL concept_id to a fixed sentinel inside the index key.
CREATE UNIQUE INDEX IF NOT EXISTS tank_pairs_unique_by_context_orientation
ON public.tank_pairs (
  mother_tank_id,
  father_tank_id,
  role_orientation,
  (COALESCE(concept_id, '00000000-0000-0000-0000-000000000000'::uuid))
);

-- 5) Try to drop the legacy containers table (guarded; skip if referenced)
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema='public' AND table_name='containers'
  ) THEN
    BEGIN
      EXECUTE 'DROP TABLE public.containers';
    EXCEPTION WHEN others THEN
      RAISE NOTICE 'Skipping drop of public.containers (still referenced).';
    END;
  END IF;
END$$;

COMMIT;
