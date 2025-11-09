ALTER TABLE public.plate_slots      VALIDATE CONSTRAINT fk_plate_slots_fish_code;
ALTER TABLE public.crosses          VALIDATE CONSTRAINT fk_crosses_tank_pair_code;
ALTER TABLE public.clutch_instances VALIDATE CONSTRAINT fk_clutch_instances_tank_pair_code;
ALTER TABLE public.rnas             VALIDATE CONSTRAINT fk_rnas_base_plasmid_code;
ALTER TABLE public.join_clutch_treatments VALIDATE CONSTRAINT fk_join_clutch_treatments_treat_code;
