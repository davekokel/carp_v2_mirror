BEGIN;

CREATE OR REPLACE FUNCTION public.ensure_active_tank_for_fish(p_fish_code text)
RETURNS uuid
LANGUAGE plpgsql
AS $$
DECLARE
  v_existing uuid;
  v_next_num int;
  v_new_id   uuid;
BEGIN
  IF p_fish_code IS NULL OR btrim(p_fish_code) = '' THEN
    RAISE EXCEPTION 'ensure_active_tank_for_fish(): p_fish_code is required';
  END IF;

  -- return an existing active tank for this fish_code if present (most-recent)
  SELECT t.id INTO v_existing
  FROM public.tanks t
  WHERE t.tank_code LIKE 'TANK('||p_fish_code||')#%' AND COALESCE(t.status,'active') = 'active'
  ORDER BY t.created_at DESC
  LIMIT 1;

  IF v_existing IS NOT NULL THEN
    RETURN v_existing;
  END IF;

  -- compute next available #N for this fish_code from existing tank_code
  SELECT COALESCE(MAX( (regexp_replace(tank_code, '^.*#([0-9]+).*$', '\1'))::int ), 0)
    INTO v_next_num
  FROM public.tanks
  WHERE tank_code LIKE 'TANK('||p_fish_code||')#%';

  v_next_num := v_next_num + 1;

  INSERT INTO public.tanks (tank_code, status)
  VALUES ('TANK('||p_fish_code||')#'||v_next_num::text, 'active')
  RETURNING id INTO v_new_id;

  RETURN v_new_id;
END
$$;

COMMIT;
