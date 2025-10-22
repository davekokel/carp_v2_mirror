SET search_path=public,public;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_type t
    JOIN pg_namespace n ON n.oid=t.typnamespace
    WHERE n.nspname='public' AND t.typname='tank_status'
  ) THEN
    CREATE TYPE public.tank_status AS ENUM ('vacant','occupied','quarantine','maintenance','retired','decommissioned');
  END IF;
END $$;

DROP VIEW IF EXISTS public.v_tank_occupancy;
DROP VIEW IF EXISTS public.v_tanks_current_status;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='tanks') THEN
    CREATE TABLE public.tanks (
      tank_id bigserial PRIMARY KEY,
      tank_code text UNIQUE NOT NULL,
      rack text,
      position text,
      created_at timestamptz NOT NULL DEFAULT now(),
      created_by uuid DEFAULT auth.uid()
    );
    CREATE UNIQUE INDEX IF NOT EXISTS ux_tanks_tank_code ON public.tanks(tank_code);
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='fish_tank_assignments') THEN
    CREATE TABLE public.fish_tank_assignments (
      fish_id bigint NOT NULL REFERENCES public.fish(id) ON DELETE CASCADE,
      tank_id bigint NOT NULL REFERENCES public.tanks(tank_id) ON DELETE CASCADE,
      start_at timestamptz NOT NULL DEFAULT now(),
      end_at timestamptz,
      note text,
      created_at timestamptz NOT NULL DEFAULT now(),
      created_by uuid DEFAULT auth.uid(),
      CHECK (end_at IS NULL OR end_at > start_at)
    );
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS ix_fta_fish_open ON public.fish_tank_assignments(fish_id) WHERE end_at IS NULL;
CREATE INDEX IF NOT EXISTS ix_fta_tank_open ON public.fish_tank_assignments(tank_id) WHERE end_at IS NULL;
CREATE UNIQUE INDEX IF NOT EXISTS ux_fta_fish_one_open ON public.fish_tank_assignments(fish_id) WHERE end_at IS NULL;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='tank_status_history') THEN
    CREATE TABLE public.tank_status_history (
      tank_id bigint NOT NULL REFERENCES public.tanks(tank_id) ON DELETE CASCADE,
      status public.tank_status NOT NULL,
      reason text,
      changed_at timestamptz NOT NULL DEFAULT now(),
      changed_by uuid DEFAULT auth.uid(),
      PRIMARY KEY (tank_id, changed_at)
    );
    CREATE INDEX ix_tsh_tank_id_changed_at ON public.tank_status_history(tank_id, changed_at DESC);
  END IF;
END $$;

CREATE OR REPLACE VIEW public.v_tank_occupancy AS
SELECT t.tank_id, t.tank_code,
       count(*) FILTER (WHERE a.end_at IS NULL)::int AS n_fish_open
FROM public.tanks t
LEFT JOIN public.fish_tank_assignments a ON a.tank_id = t.tank_id AND a.end_at IS NULL
GROUP BY t.tank_id, t.tank_code;

CREATE OR REPLACE VIEW public.v_tanks_current_status AS
WITH last AS (
  SELECT tank_id, max(changed_at) AS changed_at
  FROM public.tank_status_history
  GROUP BY tank_id
)
SELECT t.tank_id, t.tank_code, t.rack, t.position, h.status, h.reason, h.changed_at
FROM public.tanks t
LEFT JOIN last l ON l.tank_id = t.tank_id
LEFT JOIN public.tank_status_history h ON h.tank_id = l.tank_id AND h.changed_at = l.changed_at;

CREATE OR REPLACE FUNCTION public._tank_set_status(p_tank_id bigint, p_status public.tank_status, p_reason text)
RETURNS void LANGUAGE sql AS $$
  INSERT INTO public.tank_status_history (tank_id, status, reason) VALUES (p_tank_id, p_status, p_reason)
$$;

CREATE OR REPLACE FUNCTION public._sync_tank_status_after_assignment()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE v_tank_id bigint; v_open int; v_cur_status public.tank_status;
BEGIN
  v_tank_id := COALESCE(NEW.tank_id, OLD.tank_id);
  SELECT coalesce(n_fish_open, 0) INTO v_open FROM public.v_tank_occupancy WHERE tank_id = v_tank_id;
  SELECT status INTO v_cur_status FROM public.v_tanks_current_status WHERE tank_id = v_tank_id;
  IF v_open > 0 AND (v_cur_status IS NULL OR v_cur_status <> 'occupied') THEN
    PERFORM public._tank_set_status(v_tank_id, 'occupied', 'auto: fish assigned');
  ELSIF v_open = 0 AND (v_cur_status IS NULL OR v_cur_status <> 'vacant') THEN
    PERFORM public._tank_set_status(v_tank_id, 'vacant', 'auto: all fish removed');
  END IF;
  RETURN NULL;
END $$;

DROP TRIGGER IF EXISTS trg_fta_sync_status_iud ON public.fish_tank_assignments;
CREATE TRIGGER trg_fta_sync_status_iud
AFTER INSERT OR UPDATE OR DELETE ON public.fish_tank_assignments
FOR EACH ROW EXECUTE FUNCTION public._sync_tank_status_after_assignment();

CREATE OR REPLACE FUNCTION public.ensure_tank(p_tank_code text, p_rack text DEFAULT NULL, p_position text DEFAULT NULL, p_status public.tank_status DEFAULT NULL, p_reason text DEFAULT NULL)
RETURNS bigint LANGUAGE plpgsql AS $$
DECLARE v_tank_id bigint; v_exists bigint;
BEGIN
  SELECT tank_id INTO v_exists FROM public.tanks WHERE tank_code = p_tank_code;
  IF v_exists IS NULL THEN
    INSERT INTO public.tanks(tank_code, rack, position) VALUES (p_tank_code, p_rack, p_position) RETURNING tank_id INTO v_tank_id;
    IF p_status IS NULL THEN
      PERFORM public._tank_set_status(v_tank_id, 'vacant', 'auto: created');
    ELSE
      PERFORM public._tank_set_status(v_tank_id, p_status, COALESCE(p_reason,'created'));
    END IF;
  ELSE
    v_tank_id := v_exists;
  END IF;
  RETURN v_tank_id;
END $$;

CREATE OR REPLACE FUNCTION public.move_fish_to_tank(p_fish_id bigint, p_tank_code text, p_rack text DEFAULT NULL, p_position text DEFAULT NULL, p_note text DEFAULT NULL)
RETURNS void LANGUAGE plpgsql AS $$
DECLARE v_tank_id bigint;
BEGIN
  v_tank_id := public.ensure_tank(p_tank_code, p_rack, p_position, NULL, NULL);
  UPDATE public.fish_tank_assignments SET end_at = now() WHERE fish_id = p_fish_id AND end_at IS NULL;
  INSERT INTO public.fish_tank_assignments(fish_id, tank_id, note) VALUES (p_fish_id, v_tank_id, p_note);
END $$;
