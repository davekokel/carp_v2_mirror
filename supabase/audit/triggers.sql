clutch_instances|trg_clutch_default_treated|CREATE TRIGGER trg_clutch_default_treated AFTER INSERT ON public.clutch_instances FOR EACH ROW EXECUTE FUNCTION trg_clutch_default_treated()
join_aliases|trg_enforce_join_aliases_fk|CREATE TRIGGER trg_enforce_join_aliases_fk BEFORE INSERT OR UPDATE ON public.join_aliases FOR EACH ROW EXECUTE FUNCTION enforce_join_aliases_fk()
