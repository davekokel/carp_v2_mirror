BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

DO $$
DECLARE
  has_ci         boolean;
  has_ci_clutch  boolean;
  has_ci_cross   boolean;
  view_sql       text;
  counts_sql     text;
BEGIN
  SELECT EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema='public' AND table_name='clutch_instances'
  ) INTO has_ci;

  IF has_ci THEN
    SELECT EXISTS (
      SELECT 1 FROM information_schema.columns
      WHERE table_schema='public' AND table_name='clutch_instances' AND column_name='clutch_id'
    ) INTO has_ci_clutch;

    SELECT EXISTS (
      SELECT 1 FROM information_schema.columns
      WHERE table_schema='public' AND table_name='clutch_instances' AND column_name='cross_id'
    ) INTO has_ci_cross;
  ELSE
    has_ci_clutch := false;
    has_ci_cross  := false;
  END IF;

  IF has_ci_clutch THEN
    counts_sql := $C$
      counts AS (
        SELECT ci.clutch_id, count(*)::int AS n_instances
        FROM public.clutch_instances ci
        GROUP BY ci.clutch_id
      )
    $C$;
  ELSIF has_ci_cross THEN
    counts_sql := $C$
      counts AS (
        SELECT c.clutch_id, count(ci.*)::int AS n_instances
        FROM public.clutches c
        LEFT JOIN public.clutch_instances ci ON ci.cross_id = c.cross_id
        GROUP BY c.clutch_id
      )
    $C$;
  ELSE
    counts_sql := $C$
      counts AS (
        SELECT c.clutch_id, 0::int AS n_instances
        FROM public.clutches c
      )
    $C$;
  END IF;

  view_sql := format($V$
    CREATE OR REPLACE VIEW public.v_clutches AS
    WITH %s,
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
      t.fish_code AS fish_code,
      c.date_birth,
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
  $V$, counts_sql);

  EXECUTE view_sql;
END$$;

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
