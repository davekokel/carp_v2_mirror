BEGIN;
CREATE OR REPLACE FUNCTION public.fish_insert_autotank()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  INSERT INTO public.tanks (tank_id, tank_code, fish_code, rack, position, created_at, created_by)
  VALUES (
    gen_random_uuid(),
    format('TANK-%s-#1', NEW.fish_code),
    NEW.fish_code,
    NULL, NULL,
    now(),
    NEW.created_by
  )
  ON CONFLICT DO NOTHING;
  RETURN NEW;
END;
$$;

-- re-link trigger if dropped
DROP TRIGGER IF EXISTS trg_fish_autotank ON public.fish;
CREATE TRIGGER trg_fish_autotank
AFTER INSERT ON public.fish
FOR EACH ROW
EXECUTE FUNCTION public.fish_insert_autotank();
COMMIT;
