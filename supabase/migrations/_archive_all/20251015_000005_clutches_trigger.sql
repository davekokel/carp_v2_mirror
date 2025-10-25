DROP TRIGGER IF EXISTS trg_clutch_instance_code_fill ON public.clutches;
CREATE TRIGGER trg_clutch_instance_code_fill
AFTER INSERT OR UPDATE ON public.clutches
FOR EACH ROW EXECUTE FUNCTION public.trg_clutch_instance_code_fill();
