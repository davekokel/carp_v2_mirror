BEGIN;

CREATE TABLE IF NOT EXISTS public.tanks (
  tank_uuid uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tank_code text UNIQUE,
  created_at timestamptz DEFAULT now()
);

ALTER TABLE public.tanks ADD COLUMN IF NOT EXISTS fish_code text;
ALTER TABLE public.tanks ADD COLUMN IF NOT EXISTS tank_num integer;
ALTER TABLE public.tanks ADD COLUMN IF NOT EXISTS status text;

UPDATE public.tanks
SET fish_code = regexp_replace(tank_code, '^.*\(([^)]+)\).*$', '\1')
WHERE fish_code IS NULL AND tank_code IS NOT NULL;

UPDATE public.tanks
SET tank_num = NULLIF(regexp_replace(tank_code, '^.*#([0-9]+).*$', '\1'), '')::int
WHERE tank_num IS NULL AND tank_code IS NOT NULL;

UPDATE public.tanks
SET status = 'active'
WHERE status IS NULL;

ALTER TABLE public.tanks
  ADD CONSTRAINT chk_tanks_status CHECK (status IN ('active','to_kill','inactive'));

CREATE UNIQUE INDEX IF NOT EXISTS uq_tanks_fish_num ON public.tanks (fish_code, tank_num);

CREATE OR REPLACE FUNCTION public.next_tank_num(p_fish_code text)
RETURNS integer
LANGUAGE sql
AS $$
  SELECT COALESCE(MAX(tank_num),0)+1 FROM public.tanks WHERE fish_code = p_fish_code
$$;

CREATE OR REPLACE FUNCTION public.tanks_bi_set_defaults()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  IF NEW.fish_code IS NULL THEN
    RAISE EXCEPTION 'fish_code is required';
  END IF;

  IF NEW.tank_num IS NULL THEN
    NEW.tank_num := public.next_tank_num(NEW.fish_code);
  END IF;

  IF NEW.status IS NULL THEN
    NEW.status := 'active';
  END IF;

  NEW.tank_code := 'TANK('||NEW.fish_code||')#'||NEW.tank_num;
  RETURN NEW;
END
$$;

DROP TRIGGER IF EXISTS trg_tanks_bi_set_defaults ON public.tanks;
CREATE TRIGGER trg_tanks_bi_set_defaults
BEFORE INSERT ON public.tanks
FOR EACH ROW
EXECUTE FUNCTION public.tanks_bi_set_defaults();

CREATE OR REPLACE FUNCTION public.ensure_active_tank_for_fish(p_fish_code text)
RETURNS uuid
LANGUAGE plpgsql
AS $$
DECLARE
  v_id uuid;
BEGIN
  SELECT tank_uuid INTO v_id
  FROM public.tanks
  WHERE fish_code = p_fish_code AND status = 'active'
  ORDER BY created_at DESC
  LIMIT 1;

  IF v_id IS NOT NULL THEN
    RETURN v_id;
  END IF;

  INSERT INTO public.tanks (fish_code, status)
  VALUES (p_fish_code, 'active')
  RETURNING tank_uuid INTO v_id;

  RETURN v_id;
END
$$;

CREATE OR REPLACE VIEW public.v_tanks AS
SELECT
  tank_uuid,
  tank_code,
  fish_code,
  status,
  created_at
FROM public.tanks;

COMMIT;
