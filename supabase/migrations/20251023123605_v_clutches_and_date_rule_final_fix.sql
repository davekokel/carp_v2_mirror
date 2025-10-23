BEGIN;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='clutches' AND column_name='date_birth'
  ) THEN
    ALTER TABLE public.clutches ADD COLUMN date_birth date;
  END IF;
END$$;

CREATE OR REPLACE VIEW public.v_clutches AS
WITH
  tc_latest AS (
    SELECT DISTINCT ON (tc.cross_id)
           tc.cross_id,
           tc.tank_id,
           tc.mom_fish_code,
           tc.dad_fish_code,
           tc.mom_tank_id,
           tc.dad_tank_id,
           tc.date_crossed,
           tc.created_at
    FROM public.tank_crosses tc
    ORDER BY tc.cross_id, tc.created_at DESC NULLS LAST
  ),
  counts AS (
    SELECT c.id AS clutch_id, count(ci.*)::int AS n_instances
    FROM public.clutches c
    LEFT JOIN public.clutch_instances ci
           ON ci.cross_instance_id = c.cross_instance_id
    GROUP BY c.id
  ),
  parents AS (
    SELECT
      tcl.cross_id,
      tcl.mom_fish_code,
      tcl.dad_fish_code,
      tm.tank_code AS mom_tank_code,
      td.tank_code AS dad_tank_code
    FROM tc_latest tcl
    LEFT JOIN public.tanks tm ON tm.tank_id = tcl.mom_tank_id
    LEFT JOIN public.tanks td ON td.tank_id = tcl.dad_tank_id
  ),
  spawn AS (
    SELECT
      tcl.cross_id,
      tcl.tank_id,
      t.tank_code,
      t.fish_code
    FROM tc_latest tcl
    LEFT JOIN public.tanks t ON t.tank_id = tcl.tank_id
  )
SELECT
  c.id              AS clutch_id,
  c.cross_id,
  c.cross_instance_id,
  sp.tank_id,
  sp.tank_code,
  sp.fish_code,
  c.date_birth,
  c.note,
  c.created_at,
  c.created_by,
  COALESCE(cnt.n_instances, 0) AS n_instances,
  p.mom_fish_code,
  p.dad_fish_code,
  p.mom_tank_code,
  p.dad_tank_code
FROM public.clutches c
LEFT JOIN counts  cnt ON cnt.clutch_id = c.id
LEFT JOIN parents p   ON p.cross_id    = c.cross_id
LEFT JOIN spawn   sp  ON sp.cross_id   = c.cross_id
ORDER BY c.created_at DESC;

WITH src AS (
  SELECT c.id AS clutch_id,
         (SELECT (tcl.date_crossed + INTERVAL '1 day')::date
            FROM public.tank_crosses tcl
           WHERE tcl.cross_id = c.cross_id
           ORDER BY tcl.created_at DESC NULLS LAST
           LIMIT 1) AS derived
  FROM public.clutches c
  WHERE c.date_birth IS NULL
)
UPDATE public.clutches c
SET date_birth = s.derived
FROM src s
WHERE s.clutch_id = c.id
  AND c.date_birth IS NULL
  AND s.derived IS NOT NULL;

CREATE OR REPLACE FUNCTION public.tg_clutches_default_date_birth() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.date_birth IS NULL THEN
    SELECT (tcl.date_crossed + INTERVAL '1 day')::date
      INTO NEW.date_birth
      FROM (
        SELECT DISTINCT ON (cross_id) cross_id, date_crossed, created_at
        FROM public.tank_crosses
        WHERE cross_id = NEW.cross_id
        ORDER BY cross_id, created_at DESC NULLS LAST
      ) tcl
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
