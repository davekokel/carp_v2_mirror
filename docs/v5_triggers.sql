CREATE TRIGGER trg_clutch_instances_bi_assign_fields CREATE TRIGGER trg_clutch_instances_bi_assign_fields BEFORE INSERT ON public.clutch_instances FOR EACH ROW EXECUTE FUNCTION clutch_instances_bi_assign_fields();
CREATE TRIGGER trg_crosses_bi_assign_code CREATE TRIGGER trg_crosses_bi_assign_code BEFORE INSERT ON public.crosses FOR EACH ROW EXECUTE FUNCTION crosses_bi_assign_code();
CREATE TRIGGER trg_enforce_join_annotations_fk CREATE CONSTRAINT TRIGGER trg_enforce_join_annotations_fk AFTER INSERT OR UPDATE ON public.join_annotations DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION enforce_join_annotations_fk();
CREATE TRIGGER trg_fish_code_default CREATE TRIGGER trg_fish_code_default BEFORE INSERT ON public.fish FOR EACH ROW EXECUTE FUNCTION trg_set_fish_code_from_uuid_base36_8();
CREATE TRIGGER trg_plates_bi_assign_code CREATE TRIGGER trg_plates_bi_assign_code BEFORE INSERT ON public.plates FOR EACH ROW EXECUTE FUNCTION plates_bi_assign_code();
CREATE TRIGGER trg_tank_pairs_bi_assign_code CREATE TRIGGER trg_tank_pairs_bi_assign_code BEFORE INSERT ON public.tank_pairs FOR EACH ROW EXECUTE FUNCTION tank_pairs_bi_assign_code();
CREATE TRIGGER trg_tanks_bi_set_defaults CREATE TRIGGER trg_tanks_bi_set_defaults BEFORE INSERT ON public.tanks FOR EACH ROW EXECUTE FUNCTION tanks_bi_set_defaults();
CREATE TRIGGER trg_tc_ai_baseline CREATE TRIGGER trg_tc_ai_baseline AFTER INSERT ON public.clutch_instances FOR EACH ROW EXECUTE FUNCTION treated_clutches_ai_baseline();
CREATE TRIGGER trg_treated_clutches_bi_assign_code CREATE TRIGGER trg_treated_clutches_bi_assign_code BEFORE INSERT ON public.treated_clutches FOR EACH ROW EXECUTE FUNCTION treated_clutches_bi_assign_code();
