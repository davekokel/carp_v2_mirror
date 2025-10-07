BEGIN;

-- counter table and code generator (TANK-YY-####)
CREATE TABLE IF NOT EXISTS public.tank_year_counters (
  year integer PRIMARY KEY,
  n    bigint   NOT NULL DEFAULT 0
);

CREATE OR REPLACE FUNCTION public.gen_tank_code()
RETURNS text LANGUAGE plpgsql AS $$
DECLARE
  yy int := (extract(year from now())::int % 100);
  c  bigint;
BEGIN
  INSERT INTO public.tank_year_counters(year,n) VALUES (yy,0)
  ON CONFLICT (year) DO NOTHING;

  UPDATE public.tank_year_counters
     SET n = tank_year_counters.n + 1
   WHERE year = yy
  RETURNING n INTO c;

  RETURN format('TANK-%02s-%04s', yy, c);
END$$;

-- add column + unique index
ALTER TABLE public.containers
  ADD COLUMN IF NOT EXISTS tank_code text;
CREATE UNIQUE INDEX IF NOT EXISTS uq_containers_tank_code
  ON public.containers(tank_code)
  WHERE tank_code IS NOT NULL;

-- ensure our "volume-aware" creator sets tank_code on insert
CREATE OR REPLACE FUNCTION public.ensure_inventory_tank_v(
  p_label    text,
  p_by       text,
  p_status   container_status DEFAULT 'active',
  p_volume_l integer          DEFAULT NULL
) RETURNS uuid LANGUAGE plpgsql AS $$
DECLARE
  rid uuid;
BEGIN
  SELECT id_uuid INTO rid
    FROM public.containers
   WHERE container_type='inventory_tank'
     AND COALESCE(label,'') = COALESCE(p_label,'')
   ORDER BY created_at ASC
   LIMIT 1;

  IF rid IS NULL THEN
    INSERT INTO public.containers (container_type, label, tank_code, status, created_by, tank_volume_l, note)
    VALUES ('inventory_tank', p_label, public.gen_tank_code(), COALESCE(p_status,'active'), p_by, p_volume_l, NULL)
    RETURNING id_uuid INTO rid;
  ELSE
    IF p_status='active' THEN
      PERFORM public.mark_container_active(rid, p_by);
    END IF;
    UPDATE public.containers
       SET tank_volume_l = COALESCE(tank_volume_l, p_volume_l)
     WHERE id_uuid = rid;
  END IF;

  RETURN rid;
END$$;

-- text wrapper stays the same
CREATE OR REPLACE FUNCTION public.ensure_inventory_tank_v_text(
  p_label text, p_by text, p_status text, p_volume_l integer
) RETURNS uuid LANGUAGE plpgsql AS $$
BEGIN
  RETURN public.ensure_inventory_tank_v(p_label, p_by, p_status::container_status, p_volume_l);
END$$;

COMMIT;
