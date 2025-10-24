BEGIN;

-- 1) Drop legacy/duplicate triggers on public.tank_pairs (if they exist)
DO $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM pg_trigger t
    JOIN pg_class c ON c.oid = t.tgrelid
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = 'public' AND c.relname = 'tank_pairs' AND t.tgname = 'trg_tank_pairs_set_code'
  ) THEN
    EXECUTE 'DROP TRIGGER IF EXISTS trg_tank_pairs_set_code ON public.tank_pairs';
    RAISE NOTICE 'Dropped legacy trigger: trg_tank_pairs_set_code';
  END IF;

  IF EXISTS (
    SELECT 1
    FROM pg_trigger t
    JOIN pg_class c ON c.oid = t.tgrelid
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = 'public' AND c.relname = 'tank_pairs' AND t.tgname = 'trg_tank_pairs_immutable_code'
  ) THEN
    EXECUTE 'DROP TRIGGER IF EXISTS trg_tank_pairs_immutable_code ON public.tank_pairs';
    RAISE NOTICE 'Dropped legacy trigger: trg_tank_pairs_immutable_code';
  END IF;

  -- Optional: if you have a duplicate updated_at trigger alongside trg_set_updated_at, drop it
  IF EXISTS (
    SELECT 1
    FROM pg_trigger t
    JOIN pg_class c ON c.oid = t.tgrelid
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = 'public' AND c.relname = 'tank_pairs' AND t.tgname = 'trg_tp_set_updated_at'
  ) THEN
    EXECUTE 'DROP TRIGGER IF EXISTS trg_tp_set_updated_at ON public.tank_pairs';
    RAISE NOTICE 'Dropped duplicate trigger: trg_tp_set_updated_at';
  END IF;
END
$$;

-- 2) Optionally drop the old code function if it exists (no-op if absent)
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM pg_proc p
    JOIN pg_namespace n ON n.oid = p.pronamespace
    WHERE n.nspname='public' AND p.proname = 'trg_tank_pairs_set_code'
  ) THEN
    EXECUTE 'DROP FUNCTION public.trg_tank_pairs_set_code()';
    RAISE NOTICE 'Dropped legacy function: public.trg_tank_pairs_set_code()';
  END IF;
END
$$;

-- 3) Normalize/Backfill: assign tp_seq per fish_pair and set tank_pair_code = TP-<fish_pair_code>-<n>
--    Deterministic order: created_at, id. This preserves append-only semantics and ensures uniqueness.
LOCK TABLE public.tank_pairs IN ROW EXCLUSIVE MODE;

WITH ranked AS (
  SELECT
    tp.id,
    tp.fish_pair_id,
    fp.fish_pair_code,
    ROW_NUMBER() OVER (PARTITION BY tp.fish_pair_id ORDER BY tp.created_at, tp.id) AS rn
  FROM public.tank_pairs tp
  JOIN public.fish_pairs fp ON fp.fish_pair_id = tp.fish_pair_id
)
UPDATE public.tank_pairs AS tp
SET
  tp_seq         = r.rn,
  tank_pair_code = 'TP-' || r.fish_pair_code || '-' || r.rn::text
FROM ranked AS r
WHERE tp.id = r.id
  AND (
        tp.tp_seq         IS DISTINCT FROM r.rn
     OR tp.tank_pair_code IS DISTINCT FROM ('TP-' || r.fish_pair_code || '-' || r.rn::text)
  );

COMMIT;
