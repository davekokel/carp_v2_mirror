BEGIN;

-- A) Canonical overview view
CREATE OR REPLACE VIEW public.v_clutches AS
WITH counts AS (
  SELECT ci.clutch_id, count(*)::int AS n_instances
  FROM public.clutch_instances ci
  GROUP BY ci.clutch_id
),
parents AS (
  SELECT
    tc.cross_id,
    tc.mom_fish_code,
    tc.dad_fish_code,
    tm.tank_code AS mom_tank_code,
    td.tank_code AS dad_tank_code
  FROM public.tank_crosses tc
  LEFT JOIN public.tanks tm ON tm.tank_id = tc.mom_tank_id
  LEFT JOIN public.tanks td ON td.tank_id = tc.dad_tank_id
)
SELECT
  c.clutch_id,
  c.cross_id,
  c.tank_id,
  t.tank_code,
  c.date_birth,              -- canonical clutch date
  c.note,
  c.created_at,
  c.created_by,
  COALESCE(cnt.n_instances,0) AS n_instances,
  p.mom_fish_code,
  p.dad_fish_code,
  p.mom_tank_code,
  p.dad_tank_code
FROM public.clutches c
LEFT JOIN counts  cnt ON cnt.clutch_id = c.clutch_id
LEFT JOIN parents p   ON p.cross_id    = c.cross_id
LEFT JOIN public.tanks t ON t.tank_id  = c.tank_id
ORDER BY c.created_at DESC;

-- B1) Backfill existing rows: date_birth = (latest tank_crosses.date_crossed + 1 day) when null
WITH src AS (
  SELECT c.clutch_id,
         (SELECT (tc.date_crossed + INTERVAL '1 day')::date
            FROM public.tank_crosses tc
           WHERE tc.cross_id = c.cross_id
           ORDER BY tc.created_at DESC NULLS LAST
           LIMIT 1) AS derived
  FROM public.clutches c
  WHERE c.date_birth IS NULL
)
UPDATE public.clutches c
SET date_birth = s.derived
FROM src s
WHERE s.clutch_id = c.clutch_id
  AND c.date_birth IS NULL
  AND s.derived IS NOT NULL;

-- B2) Trigger to enforce the rule on future writes
CREATE OR REPLACE FUNCTION public.tg_clutches_default_date_birth() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.date_birth IS NULL THEN
    SELECT (tc.date_crossed + INTERVAL '1 day')::date
      INTO NEW.date_birth
      FROM public.tank_crosses tc
     WHERE tc.cross_id = NEW.cross_id
     ORDER BY tc.created_at DESC NULLS LAST
     LIMIT 1;
  END IF;
  RETURN NEW;
END$$;

DROP TRIGGER IF EXISTS tg_clutches_default_date_birth ON public.clutches;
CREATE TRIGGER tg_clutches_default_date_birth
BEFORE INSERT OR UPDATE OF cross_id, date_birth
ON public.clutches
FOR EACH ROW
EXECUTE FUNCTION public.tg_clutches_default_date_birth();

COMMIT;
