SET search_path=public,public;

CREATE OR REPLACE FUNCTION public._sync_tank_status_after_assignment()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
  v_tank_id bigint;
  v_open int;
  v_cur_status public.tank_status;
  v_new_status public.tank_status;
BEGIN
  v_tank_id := COALESCE(NEW.tank_id, OLD.tank_id);

  SELECT count(*)::int
  INTO v_open
  FROM public.fish_tank_assignments
  WHERE tank_id = v_tank_id
    AND end_at IS NULL;

  SELECT status
  INTO v_cur_status
  FROM public.v_tanks_current_status
  WHERE tank_id = v_tank_id;

  IF v_open > 0 THEN
    v_new_status := 'occupied';
  ELSE
    v_new_status := 'vacant';
  END IF;

  IF v_cur_status IS DISTINCT FROM v_new_status THEN
    PERFORM public._tank_set_status(v_tank_id, v_new_status, CASE WHEN v_open > 0 THEN 'auto: fish assigned' ELSE 'auto: all fish removed' END);
  END IF;

  RETURN NULL;
END
$$;
