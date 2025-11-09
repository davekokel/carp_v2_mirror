BEGIN;
DROP TRIGGER IF EXISTS trg_fish_code_default ON public.fish;
CREATE TRIGGER trg_fish_code_default
BEFORE INSERT ON public.fish
FOR EACH ROW
EXECUTE FUNCTION public.trg_set_fish_code_from_uuid_base36_8();
COMMIT;
