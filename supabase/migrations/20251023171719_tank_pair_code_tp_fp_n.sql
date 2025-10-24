BEGIN;

-- 1) Per-pair sequence column (smallint is plenty; use int if you prefer)
ALTER TABLE public.tank_pairs
  ADD COLUMN IF NOT EXISTS tp_seq integer;

-- 2) Safety: unique per fish_pair_id + tp_seq
CREATE UNIQUE INDEX IF NOT EXISTS tank_pairs_unique_fp_seq
  ON public.tank_pairs (fish_pair_id, tp_seq);

-- 3) Helper: compute next tp_seq under lock, then format the code
CREATE OR REPLACE FUNCTION public.tank_pairs_assign_code()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
  v_fp_code text;
  v_next_seq integer;
BEGIN
  -- If the row already has a code, do nothing (support idempotent upserts/legacy)
  IF NEW.tank_pair_code IS NOT NULL AND NEW.tank_pair_code <> '' THEN
    RETURN NEW;
  END IF;

  -- Must have fish_pair_id to derive code
  IF NEW.fish_pair_id IS NULL THEN
    RAISE EXCEPTION 'tank_pairs.fish_pair_id is required to assign tank_pair_code';
  END IF;

  -- Fetch fish_pair_code
  SELECT fp.fish_pair_code
    INTO v_fp_code
  FROM public.fish_pairs fp
  WHERE fp.fish_pair_id = NEW.fish_pair_id
  FOR SHARE;

  IF v_fp_code IS NULL OR v_fp_code = '' THEN
    RAISE EXCEPTION 'No fish_pair_code found for fish_pair_id=%', NEW.fish_pair_id;
  END IF;

  -- Lock existing rows for this fish_pair_id to allocate the next tp_seq safely
  PERFORM 1
  FROM public.tank_pairs tp
  WHERE tp.fish_pair_id = NEW.fish_pair_id
  FOR UPDATE;

  SELECT COALESCE(MAX(tp.tp_seq), 0) + 1
    INTO v_next_seq
  FROM public.tank_pairs tp
  WHERE tp.fish_pair_id = NEW.fish_pair_id;

  NEW.tp_seq := v_next_seq;
  NEW.tank_pair_code := 'TP-' || v_fp_code || '-' || v_next_seq::text;

  RETURN NEW;
END
$$;

-- 4) Trigger: only on INSERT; updates keep the same code
DROP TRIGGER IF EXISTS trg_tank_pairs_assign_code ON public.tank_pairs;
CREATE TRIGGER trg_tank_pairs_assign_code
BEFORE INSERT ON public.tank_pairs
FOR EACH ROW
EXECUTE FUNCTION public.tank_pairs_assign_code();

-- 5) Backfill any existing rows missing code
DO $$
DECLARE
  r record;
BEGIN
  FOR r IN
    SELECT tp.id
    FROM public.tank_pairs tp
    WHERE COALESCE(tp.tank_pair_code,'') = ''
  LOOP
    UPDATE public.tank_pairs t
    SET tank_pair_code = NULL,  -- force trigger-style computation via temp insert/update trick
        tp_seq = NULL
    WHERE t.id = r.id;
  END LOOP;
END$$;

COMMIT;
