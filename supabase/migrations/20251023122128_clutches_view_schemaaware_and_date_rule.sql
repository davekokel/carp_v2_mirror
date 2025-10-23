BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Ensure clutches.date_birth exists
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='clutches') THEN
    IF NOT EXISTS (
      SELECT 1 FROM information_schema.columns
      WHERE table_schema='public' AND table_name='clutches' AND column_name='date_birth'
    ) THEN
      ALTER TABLE public.clutches ADD COLUMN date_birth date;
    END IF;
  END IF;
END$$;

-- Build v_clutches in a schema-aware way
DO $$
DECLARE
  has_clutches     bool := EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='clutches');
  has_tanks        bool := EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='tanks');
  has_crosses      bool := EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='tank_crosses');
  has_ci           bool := EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='clutch_instances');
  has_ci_clutch    bool := EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='clutch_instances' AND column_name='clutch_id');
  has_ci_cross     bool := EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='clutch_instances' AND column_name='cross_id');

  counts_cte   text;
  parents_cte  text;
  tank_select  text;
  tank_join    text;
  view_sql     text;
BEGIN
  IF NOT has_clutches THEN
    -- No clutches table: create a zero-row stub so the page can load.
    EXECUTE $V$
      CREATE OR REPLACE VIEW public.v_clutches AS
      SELECT
        NULL::uuid AS clutch_id,
        NULL::uuid AS cross_id,
        NULL::uuid AS tank_id,
        NULL::text AS tank_code,
        NULL::text AS fish_code,
        NULL::date AS date_birth,
        NULL::text AS note,
        NULL::timestamptz AS created_at,
        NULL::uuid AS created_by,
        0::int AS n_instances,
        NULL::text AS mom_fish_code,
        NULL::text AS dad_fish_code,
        NULL::text AS mom_tank_code,
        NULL::text AS dad_tank_code
      WHERE false;
    $V$;
    RETURN;
  END IF;

  -- counts CTE
  IF has_ci AND has_ci_clutch THEN
    counts_cte := $C$
      counts AS (
        SELECT ci.clutch_id, count(*)::int AS n_instances
        FROM public.clutch_instances ci
        GROUP BY ci.clutch_id
      )
    $C$;
  ELSIF has_ci AND has_ci_cross THEN
    counts_cte := $C$
      counts AS (
        SELECT c.clutch_id, count(ci.*)::int AS n_instances
        FROM public.clutches c
        LEFT JOIN public.clutch_instances ci ON ci.cross_id = c.cross_id
        GROUP BY c.clutch_id
      )
    $C$;
  ELSE
    counts_cte := $C$
      counts AS (
        SELECT c.clutch_id, 0::int AS n_instances
        FROM public.clutches c
      )
    $C$;
  END IF;

  -- parents CTE
  IF has_crosses AND has_tanks THEN
    parents_cte := $P$
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
    $P$;
  ELSIF has_crosses THEN
    parents_cte := $P$
      parents AS (
        SELECT
          tc.cross_id,
          tc.mom_fish_code,
          tc.dad_fish_code,
          NULL::text AS mom_tank_code,
          NULL::text AS dad_tank_code
        FROM public.tank_crosses tc
      )
    $P$;
  ELSE
    parents_cte := $P$
      parents AS (
        SELECT NULL::uuid AS cross_id,
               NULL::text AS mom_fish_code,
               NULL::text AS dad_fish_code,
               NULL::text AS mom_tank_code,
               NULL::text AS dad_tank_code
        WHERE false
      )
    $P$;
  END IF;

  -- tank fields & join
  IF has_tanks THEN
    tank_select := 't.tank_code, t.fish_code';
    tank_join   := 'LEFT JOIN public.tanks t ON t.tank_id = c.tank_id';
  ELSE
    tank_select := 'NULL::text AS tank_code, NULL::text AS fish_code';
    tank_join   := '';
  END IF;

  view_sql := format($V$
    CREATE OR REPLACE VIEW public.v_clutches AS
    WITH %s,
         %s
    SELECT
      c.clutch_id,
      c.cross_id,
      c.tank_id,
      %s,
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
    %s
    ORDER BY c.created_at DESC;
  $V$, counts_cte, parents_cte, tank_select, tank_join);

  EXECUTE view_sql;
END$$;

-- Backfill clutches.date_birth from latest cross + 1 day (when possible)
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='tank_crosses') THEN
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
  END IF;
END$$;

-- Trigger to default date_birth on future writes (safe even if tank_crosses empty)
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
