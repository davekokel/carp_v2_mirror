BEGIN;

-- ─────────────────────────────────────────────
-- clutches: add nickname + display_name
-- ─────────────────────────────────────────────
ALTER TABLE public.clutches
  ADD COLUMN IF NOT EXISTS nickname text,
  ADD COLUMN IF NOT EXISTS display_name text;

UPDATE public.clutches
SET display_name = COALESCE(
    nickname,
    clutch_code,
    TO_CHAR(clutch_date, 'YYYY-MM-DD')
)
WHERE display_name IS NULL;

-- ─────────────────────────────────────────────
-- treated_clutches_v11: add nickname + display_name
-- ─────────────────────────────────────────────
ALTER TABLE public.treated_clutches_v11
  ADD COLUMN IF NOT EXISTS nickname text,
  ADD COLUMN IF NOT EXISTS display_name text;

UPDATE public.treated_clutches_v11 tc
SET display_name = COALESCE(
    tc.nickname,
    tc.treated_clutch_code,
    tc.clutch_id::text
)
WHERE tc.display_name IS NULL;

-- ─────────────────────────────────────────────
-- clutch_selection_events_v11: add nickname + display_name
-- ─────────────────────────────────────────────
ALTER TABLE public.clutch_selection_events_v11
  ADD COLUMN IF NOT EXISTS nickname text,
  ADD COLUMN IF NOT EXISTS display_name text;

UPDATE public.clutch_selection_events_v11
SET display_name = COALESCE(
    nickname,
    selection_label,
    selection_kind
)
WHERE display_name IS NULL;

-- ─────────────────────────────────────────────
-- tank_pairs: add nickname + display_name
-- ─────────────────────────────────────────────
ALTER TABLE public.tank_pairs
  ADD COLUMN IF NOT EXISTS nickname text,
  ADD COLUMN IF NOT EXISTS display_name text;

UPDATE public.tank_pairs
SET display_name = COALESCE(
    nickname,
    tank_pair_code
)
WHERE display_name IS NULL;

-- ─────────────────────────────────────────────
-- crosses: add nickname + display_name
-- ─────────────────────────────────────────────
ALTER TABLE public.crosses
  ADD COLUMN IF NOT EXISTS nickname text,
  ADD COLUMN IF NOT EXISTS display_name text;

UPDATE public.crosses
SET display_name = COALESCE(
    nickname,
    cross_run_code,
    TO_CHAR(cross_date, 'YYYY-MM-DD')
)
WHERE display_name IS NULL;

COMMIT;
